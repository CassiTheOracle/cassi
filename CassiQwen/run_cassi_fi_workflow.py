from __future__ import annotations

import argparse
import base64
import contextlib
import copy
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from cassi_qi_bootstrap import (
    CANONICAL_CODEC_SCHEMA,
    MAX_CANONICAL_BYTES,
    MAX_CANONICAL_DEPTH,
    MAX_CANONICAL_INTEGER,
    canonical_hash,
    canonical_json_bytes,
)
from cassi_qi_profile import (
    CONTRACT_ROOT_BOOTSTRAP_SCHEMA,
    CONTRACT_ROOT_SCHEMA,
    PROFILE_DEFAULTS,
    PROFILE_DEFAULTS_SCHEMA,
    PROFILE_SCHEMA,
    PROFILE_SCHEMA_DOCUMENT_SCHEMA,
    PROJECTION_REGISTRY_SCHEMA,
    SCHEMA_DOCUMENT_HASH_DOMAIN,
    SCHEMA_FIXTURE_SET_HASH_DOMAIN,
    SCHEMA_MUTATION_CONTROLS_HASH_DOMAIN,
    SCHEMA_OBJECT_CLASSES,
    SCHEMA_REGISTRY_ENTRY_HASH_DOMAIN,
    SCHEMA_REGISTRY_ENTRY_KEYS,
    SCHEMA_REGISTRY_SCHEMA,
    SEMANTIC_PROJECTIONS,
    W0_HISTORICAL_MANIFEST_SHA256,
    W0_RUN_ID,
    QiFlowProfile,
    bootstrap_identity,
    build_contract_root,
    derive_rectangular_profile_overrides,
    load_development_profile,
    validate_contract_root,
    validate_profile,
)


_REPOSITORY = Path(__file__).resolve().parent
_DIAG = _REPOSITORY / "_diag"
_SOURCE_REGISTRY = _REPOSITORY / "cassi-fi-schema-registry"
_DEVELOPMENT_PROFILE = _REPOSITORY / "cassi-qi-flow-development.json"
_PROFILE_OUTPUT = _DIAG / "cassi-qi-flow-development.json"
_WORKFLOW_STATUS_SCHEMA = "cassi.qi-flow-fi-status.v1"
_PROFILE_RECEIPT_SCHEMA = "cassi.qi-flow-fi-profile-receipt.v1"
_G1_RECEIPT_SCHEMA = "cassi.qi-flow-fi-g1-receipt.v1"
_WP_RECEIPT_SCHEMA = "cassi.qi-flow-fi-work-package-receipt.v1"
_DELIVERY_RECEIPT_SCHEMA = "cassi.qi-flow-fi-delivery-receipt.v1"
_BATCH_RECEIPT_SCHEMA = "cassi.qi-flow-fi-batch-receipt.v1"
_REGISTRY_SHARD_SCHEMA = "cassi.qi-flow-schema-registry-shard.v1"
_WORKFLOW_STATUS_DOMAIN = _WORKFLOW_STATUS_SCHEMA
_PROFILE_RECEIPT_DOMAIN = _PROFILE_RECEIPT_SCHEMA
_G1_RECEIPT_DOMAIN = _G1_RECEIPT_SCHEMA
_WP_RECEIPT_DOMAIN = _WP_RECEIPT_SCHEMA
_DELIVERY_RECEIPT_DOMAIN = _DELIVERY_RECEIPT_SCHEMA
_BATCH_RECEIPT_DOMAIN = _BATCH_RECEIPT_SCHEMA
_DOC_REQUIRED_KEYS = frozenset({"required_keys", "properties"})
_DOC_ALLOWED_KEYS = frozenset(
    {
        "schema",
        "object_schema",
        "type",
        "required_keys",
        "optional_keys",
        "nullable_keys",
        "properties",
        "definitions",
        "invariants",
        "rules",
        "additional_properties",
        "consumed_semantic_subhashes",
        "hash_domain",
        "lifecycle",
        "max_encoded_bytes",
        "max_fanout",
        "object_class",
        "self_hash_field",
        "semantic_parent_names",
        "version",
    }
)
_MAX_SCHEMA_OBJECT_BYTES = 2_097_152
_ENTRY_KEYS = tuple(SCHEMA_REGISTRY_ENTRY_KEYS)
_ENTRY_KEY_SET = frozenset(_ENTRY_KEYS)
_ALLOWED_OBJECT_CLASSES = frozenset(SCHEMA_OBJECT_CLASSES)
_PARENT_ORDER = tuple(SEMANTIC_PROJECTIONS)
_PARENT_INDEX = {name: index for index, name in enumerate(_PARENT_ORDER)}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA_VERSION_RE = re.compile(r"\.v([1-9][0-9]*)$")
_FINITE_BITS_RE = re.compile(r"^f(?:32|64):[0-9a-f]+$")
_NORMATIVE_SCHEMA_NAMES = (
    "cassi.canonical-json.v1",
    "cassi.qi-flow-action-discriminability.v1",
    "cassi.qi-flow-action-prediction.v1",
    "cassi.qi-flow-action-proposal.v1",
    "cassi.qi-flow-action.v1",
    "cassi.qi-flow-adapter-off-evidence.v1",
    "cassi.qi-flow-antialias-receipt.v1",
    "cassi.qi-flow-antialias.v1",
    "cassi.qi-flow-api-error.v1",
    "cassi.qi-flow-applied-efference.v1",
    "cassi.qi-flow-artifact-cleanup.v1",
    "cassi.qi-flow-backend-receipt.v1",
    "cassi.qi-flow-boundary-permeability-profile.v1",
    "cassi.qi-flow-boundary-transfer.v1",
    "cassi.qi-flow-candidate-result.v1",
    "cassi.qi-flow-capability-matrix.v1",
    "cassi.qi-flow-capacity-ladder.v1",
    "cassi.qi-flow-certificate-extension.v1",
    "cassi.qi-flow-chat-request.v1",
    "cassi.qi-flow-chat-response.v1",
    "cassi.qi-flow-chat-turn.v2",
    "cassi.qi-flow-checkpoint.v1",
    "cassi.qi-flow-clock-time.v1",
    "cassi.qi-flow-clock.v1",
    "cassi.qi-flow-command-inputs.v1",
    "cassi.qi-flow-contract-root-bootstrap.v1",
    "cassi.qi-flow-contract-root.v1",
    "cassi.qi-flow-conversion-profile.v1",
    "cassi.qi-flow-decision.v1",
    "cassi.qi-flow-delayed-influence.v1",
    "cassi.qi-flow-dependency-manifest.v1",
    "cassi.qi-flow-displacement.v2",
    "cassi.qi-flow-dynamic-port-frame.v1",
    "cassi.qi-flow-engineering-board.v1",
    "cassi.qi-flow-execution-schedule.v1",
    "cassi.qi-flow-failure.v1",
    "cassi.qi-flow-field-experience-plan.v1",
    "cassi.qi-flow-forgetting.v1",
    "cassi.qi-flow-gate-status.v1",
    "cassi.qi-flow-health.v1",
    "cassi.qi-flow-historical-v2-checkpoint-index.v1",
    "cassi.qi-flow-historical-v2-manifest.v1",
    "cassi.qi-flow-historical-v2-source-index.v1",
    "cassi.qi-flow-hodge-receipt.v1",
    "cassi.qi-flow-indeterminate-world-effect.v1",
    "cassi.qi-flow-ingress-journal.v1",
    "cassi.qi-flow-ledger.v1",
    "cassi.qi-flow-manifest.v1",
    "cassi.qi-flow-motor-port-reaction.v1",
    "cassi.qi-flow-multimodal-binding.v1",
    "cassi.qi-flow-no-sample.v1",
    "cassi.qi-flow-numerical-certificate.v1",
    "cassi.qi-flow-object-index.v1",
    "cassi.qi-flow-openai-api.v1",
    "cassi.qi-flow-outbox-clear.v1",
    "cassi.qi-flow-ownership.v1",
    "cassi.qi-flow-packet.v1",
    "cassi.qi-flow-profile-projections.v1",
    "cassi.qi-flow-profile.v1",
    "cassi.qi-flow-raw-retention-policy.v1",
    "cassi.qi-flow-readme-verification.v1",
    "cassi.qi-flow-release-board.v1",
    "cassi.qi-flow-release-result.v1",
    "cassi.qi-flow-remap.v1",
    "cassi.qi-flow-request-record.v1",
    "cassi.qi-flow-response-record.v1",
    "cassi.qi-flow-retention-phase-slip.v1",
    "cassi.qi-flow-retention-receipt.v1",
    "cassi.qi-flow-retention-reset.v1",
    "cassi.qi-flow-run-index.v1",
    "cassi.qi-flow-runtime-config.v1",
    "cassi.qi-flow-scale-geometry-comparison.v1",
    "cassi.qi-flow-scale-geometry.v1",
    "cassi.qi-flow-scattering-receipt.v1",
    "cassi.qi-flow-schema-registry.v1",
    "cassi.qi-flow-semantic-subhashes.v1",
    "cassi.qi-flow-sensory-openness.v1",
    "cassi.qi-flow-session-storage.v1",
    "cassi.qi-flow-session.v3",
    "cassi.qi-flow-source-identity.v1",
    "cassi.qi-flow-source-replay.v1",
    "cassi.qi-flow-space-scale-receipt.v1",
    "cassi.qi-flow-sse-frame.v1",
    "cassi.qi-flow-stability-envelope.v1",
    "cassi.qi-flow-stage-spec.v1",
    "cassi.qi-flow-state-lineage-fork-receipt.v1",
    "cassi.qi-flow-state.v3",
    "cassi.qi-flow-step.v1",
    "cassi.qi-flow-text-codebook-packing.v1",
    "cassi.qi-flow-text-event.v2",
    "cassi.qi-flow-text-ownership.v1",
    "cassi.qi-flow-text-result.v2",
    "cassi.qi-flow-tick-ack.v1",
    "cassi.qi-flow-tick-intent.v1",
    "cassi.qi-flow-tick-outbox.v1",
    "cassi.qi-flow-toolchain.v1",
    "cassi.qi-flow-topology-receipt.v1",
    "cassi.qi-flow-transaction-model-receipt.v1",
    "cassi.qi-flow-watermark.v1",
    "cassi.qi-world-action-descriptors.v1",
    "cassi.qi-world-advance-tick.v1",
    "cassi.qi-world-close-ack.v1",
    "cassi.qi-world-close.v1",
    "cassi.qi-world-describe-actions.v1",
    "cassi.qi-world-error.v1",
    "cassi.qi-world-frame.v1",
    "cassi.qi-world-heartbeat-ack.v1",
    "cassi.qi-world-heartbeat.v1",
    "cassi.qi-world-hello-ack.v1",
    "cassi.qi-world-hello.v1",
    "cassi.qi-world-observation-complete.v1",
    "cassi.qi-world-observation.v1",
    "cassi.qi-world-observe-request.v1",
    "cassi.qi-world-resolve-tick.v1",
    "cassi.qi-world-tick-complete.v1",
    "cassi.qi-world-wire.v1",
)

_SCHEMA_CLASSIFICATION = {
    "cassi.canonical-json.v1": "bootstrap-object",
    "cassi.qi-flow-action-discriminability.v1": "indexed-receipt",
    "cassi.qi-flow-action-prediction.v1": "immutable-spec",
    "cassi.qi-flow-action-proposal.v1": "indexed-receipt",
    "cassi.qi-flow-action.v1": "protocol-object",
    "cassi.qi-flow-adapter-off-evidence.v1": "indexed-receipt",
    "cassi.qi-flow-antialias-receipt.v1": "indexed-receipt",
    "cassi.qi-flow-antialias.v1": "immutable-spec",
    "cassi.qi-flow-api-error.v1": "protocol-object",
    "cassi.qi-flow-applied-efference.v1": "indexed-receipt",
    "cassi.qi-flow-artifact-cleanup.v1": "indexed-receipt",
    "cassi.qi-flow-backend-receipt.v1": "indexed-receipt",
    "cassi.qi-flow-boundary-permeability-profile.v1": "profile-contract",
    "cassi.qi-flow-boundary-transfer.v1": "indexed-receipt",
    "cassi.qi-flow-candidate-result.v1": "gate-artifact",
    "cassi.qi-flow-capability-matrix.v1": "manifest",
    "cassi.qi-flow-capacity-ladder.v1": "indexed-receipt",
    "cassi.qi-flow-certificate-extension.v1": "immutable-spec",
    "cassi.qi-flow-chat-request.v1": "protocol-object",
    "cassi.qi-flow-chat-response.v1": "protocol-object",
    "cassi.qi-flow-chat-turn.v2": "indexed-receipt",
    "cassi.qi-flow-checkpoint.v1": "checkpoint",
    "cassi.qi-flow-clock-time.v1": "protocol-object",
    "cassi.qi-flow-clock.v1": "immutable-spec",
    "cassi.qi-flow-command-inputs.v1": "manifest",
    "cassi.qi-flow-contract-root-bootstrap.v1": "bootstrap-object",
    "cassi.qi-flow-contract-root.v1": "profile-contract",
    "cassi.qi-flow-conversion-profile.v1": "immutable-spec",
    "cassi.qi-flow-decision.v1": "indexed-receipt",
    "cassi.qi-flow-delayed-influence.v1": "indexed-receipt",
    "cassi.qi-flow-dependency-manifest.v1": "manifest",
    "cassi.qi-flow-displacement.v2": "indexed-receipt",
    "cassi.qi-flow-dynamic-port-frame.v1": "protocol-object",
    "cassi.qi-flow-engineering-board.v1": "gate-artifact",
    "cassi.qi-flow-execution-schedule.v1": "immutable-spec",
    "cassi.qi-flow-failure.v1": "indexed-receipt",
    "cassi.qi-flow-field-experience-plan.v1": "immutable-spec",
    "cassi.qi-flow-forgetting.v1": "indexed-receipt",
    "cassi.qi-flow-gate-status.v1": "gate-artifact",
    "cassi.qi-flow-health.v1": "indexed-receipt",
    "cassi.qi-flow-historical-v2-checkpoint-index.v1": "manifest",
    "cassi.qi-flow-historical-v2-manifest.v1": "manifest",
    "cassi.qi-flow-historical-v2-source-index.v1": "manifest",
    "cassi.qi-flow-hodge-receipt.v1": "indexed-receipt",
    "cassi.qi-flow-indeterminate-world-effect.v1": "indexed-receipt",
    "cassi.qi-flow-ingress-journal.v1": "manifest",
    "cassi.qi-flow-ledger.v1": "indexed-receipt",
    "cassi.qi-flow-manifest.v1": "manifest",
    "cassi.qi-flow-motor-port-reaction.v1": "indexed-receipt",
    "cassi.qi-flow-multimodal-binding.v1": "indexed-receipt",
    "cassi.qi-flow-no-sample.v1": "protocol-object",
    "cassi.qi-flow-numerical-certificate.v1": "immutable-spec",
    "cassi.qi-flow-object-index.v1": "manifest",
    "cassi.qi-flow-openai-api.v1": "protocol-object",
    "cassi.qi-flow-outbox-clear.v1": "indexed-receipt",
    "cassi.qi-flow-ownership.v1": "indexed-receipt",
    "cassi.qi-flow-packet.v1": "protocol-object",
    "cassi.qi-flow-profile-projections.v1": "immutable-spec",
    "cassi.qi-flow-profile.v1": "profile-contract",
    "cassi.qi-flow-raw-retention-policy.v1": "manifest",
    "cassi.qi-flow-readme-verification.v1": "gate-artifact",
    "cassi.qi-flow-release-board.v1": "gate-artifact",
    "cassi.qi-flow-release-result.v1": "gate-artifact",
    "cassi.qi-flow-remap.v1": "indexed-receipt",
    "cassi.qi-flow-request-record.v1": "protocol-object",
    "cassi.qi-flow-response-record.v1": "protocol-object",
    "cassi.qi-flow-retention-phase-slip.v1": "indexed-receipt",
    "cassi.qi-flow-retention-receipt.v1": "indexed-receipt",
    "cassi.qi-flow-retention-reset.v1": "indexed-receipt",
    "cassi.qi-flow-run-index.v1": "manifest",
    "cassi.qi-flow-runtime-config.v1": "immutable-spec",
    "cassi.qi-flow-scale-geometry-comparison.v1": "indexed-receipt",
    "cassi.qi-flow-scale-geometry.v1": "immutable-spec",
    "cassi.qi-flow-scattering-receipt.v1": "indexed-receipt",
    "cassi.qi-flow-schema-registry.v1": "manifest",
    "cassi.qi-flow-semantic-subhashes.v1": "manifest",
    "cassi.qi-flow-sensory-openness.v1": "indexed-receipt",
    "cassi.qi-flow-session-storage.v1": "immutable-spec",
    "cassi.qi-flow-session.v3": "runtime-state",
    "cassi.qi-flow-source-identity.v1": "manifest",
    "cassi.qi-flow-source-replay.v1": "immutable-spec",
    "cassi.qi-flow-space-scale-receipt.v1": "indexed-receipt",
    "cassi.qi-flow-sse-frame.v1": "protocol-object",
    "cassi.qi-flow-stability-envelope.v1": "immutable-spec",
    "cassi.qi-flow-stage-spec.v1": "immutable-spec",
    "cassi.qi-flow-state-lineage-fork-receipt.v1": "indexed-receipt",
    "cassi.qi-flow-state.v3": "runtime-state",
    "cassi.qi-flow-step.v1": "indexed-receipt",
    "cassi.qi-flow-text-codebook-packing.v1": "indexed-receipt",
    "cassi.qi-flow-text-event.v2": "indexed-receipt",
    "cassi.qi-flow-text-ownership.v1": "indexed-receipt",
    "cassi.qi-flow-text-result.v2": "indexed-receipt",
    "cassi.qi-flow-tick-ack.v1": "protocol-object",
    "cassi.qi-flow-tick-intent.v1": "protocol-object",
    "cassi.qi-flow-tick-outbox.v1": "runtime-state",
    "cassi.qi-flow-toolchain.v1": "manifest",
    "cassi.qi-flow-topology-receipt.v1": "indexed-receipt",
    "cassi.qi-flow-transaction-model-receipt.v1": "indexed-receipt",
    "cassi.qi-flow-watermark.v1": "protocol-object",
    "cassi.qi-world-action-descriptors.v1": "protocol-object",
    "cassi.qi-world-advance-tick.v1": "protocol-object",
    "cassi.qi-world-close-ack.v1": "protocol-object",
    "cassi.qi-world-close.v1": "protocol-object",
    "cassi.qi-world-describe-actions.v1": "protocol-object",
    "cassi.qi-world-error.v1": "protocol-object",
    "cassi.qi-world-frame.v1": "protocol-object",
    "cassi.qi-world-heartbeat-ack.v1": "protocol-object",
    "cassi.qi-world-heartbeat.v1": "protocol-object",
    "cassi.qi-world-hello-ack.v1": "protocol-object",
    "cassi.qi-world-hello.v1": "protocol-object",
    "cassi.qi-world-observation-complete.v1": "protocol-object",
    "cassi.qi-world-observation.v1": "protocol-object",
    "cassi.qi-world-observe-request.v1": "protocol-object",
    "cassi.qi-world-resolve-tick.v1": "protocol-object",
    "cassi.qi-world-tick-complete.v1": "protocol-object",
    "cassi.qi-world-wire.v1": "manifest",
}


class WorkflowError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.message = str(message).replace("\n", " ").strip()
        super().__init__(self.message)


def _fail(code: str, message: str) -> None:
    raise WorkflowError(code, message)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical(value: Any, *, context: str) -> bytes:
    try:
        return canonical_json_bytes(value)
    except Exception as exc:
        _fail("NONCANONICAL_VALUE", f"{context}: {exc}")
    raise AssertionError("unreachable")


def _canonical_unbounded(value: Any, *, context: str) -> bytes:
    _validate_staging_value(value, context=context)
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8", "strict")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        _fail("NONCANONICAL_VALUE", f"{context}: {exc}")
    raise AssertionError("unreachable")


def _canonical_hash_unbounded(value: Any, domain: str, *, context: str) -> str:
    if not isinstance(domain, str) or not domain:
        _fail("HASH_DOMAIN_INVALID", f"{context} has an invalid hash domain")
    domain_bytes = domain.encode("utf-8", "strict")
    payload = _canonical_unbounded(value, context=context)
    framed = (
        len(domain_bytes).to_bytes(8, "big")
        + domain_bytes
        + len(payload).to_bytes(8, "big")
        + payload
    )
    return hashlib.sha256(framed).hexdigest()


def _safe_int(value: Any, *, context: str, minimum: int | None = None, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("NONCANONICAL_TYPE", f"{context} must be an integer")
    if not -MAX_CANONICAL_INTEGER <= value <= MAX_CANONICAL_INTEGER:
        _fail("INTEGER_RANGE", f"{context} is outside the canonical integer range")
    if minimum is not None and value < minimum:
        _fail("VALUE_RANGE", f"{context} is below its minimum")
    if maximum is not None and value > maximum:
        _fail("VALUE_RANGE", f"{context} exceeds its maximum")
    return value


def _sha(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        _fail("INVALID_SHA256", f"{context} is not a lowercase SHA-256 digest")
    return value


def _validate_staging_value(value: Any, *, context: str, depth: int = 0) -> None:
    if depth > MAX_CANONICAL_DEPTH + 2:
        _fail("NONCANONICAL_VALUE", f"{context} exceeds the staging JSON depth limit")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        if not -MAX_CANONICAL_INTEGER <= value <= MAX_CANONICAL_INTEGER:
            _fail("INTEGER_RANGE", f"{context} integer exceeds canonical range")
        return
    if isinstance(value, str):
        try:
            value.encode("utf-8", "strict")
        except UnicodeEncodeError:
            _fail("NONCANONICAL_VALUE", f"{context} contains an unpaired surrogate")
        if value.startswith("\ufeff"):
            _fail("NONCANONICAL_VALUE", f"{context} string begins with a BOM")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_staging_value(item, context=f"{context}/{index}", depth=depth + 1)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                _fail("NONCANONICAL_TYPE", f"{context} has a non-string object key")
            _validate_staging_value(key, context=f"{context}/key", depth=depth + 1)
            _validate_staging_value(item, context=f"{context}/{key}", depth=depth + 1)
        return
    _fail("NONCANONICAL_TYPE", f"{context} contains unsupported {type(value).__name__}")


def _load_json(path: Path) -> tuple[bytes, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        _fail("INPUT_READ_ERROR", f"cannot read {path}: {exc}")
    if raw.startswith(b"\xef\xbb\xbf"):
        _fail("NONCANONICAL_JSON", f"{path} begins with a UTF-8 BOM")

    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            if key in result:
                _fail("DUPLICATE_KEY", f"{path}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def parse_int(token: str) -> int:
        if token == "-0":
            _fail("NONCANONICAL_TYPE", f"{path}: negative-zero integer is forbidden")
        value = int(token, 10)
        if not -MAX_CANONICAL_INTEGER <= value <= MAX_CANONICAL_INTEGER:
            _fail("INTEGER_RANGE", f"{path}: integer exceeds canonical range")
        return value

    def parse_float(token: str) -> Any:
        _fail("NONCANONICAL_TYPE", f"{path}: decimal numbers are forbidden")
        return token

    def parse_constant(token: str) -> Any:
        _fail("NONFINITE_VALUE", f"{path}: non-finite JSON scalar {token}")
        return token

    try:
        text = raw.decode("utf-8", "strict")
        value = json.loads(
            text,
            object_pairs_hook=pairs,
            parse_int=parse_int,
            parse_float=parse_float,
            parse_constant=parse_constant,
        )
    except WorkflowError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        _fail("INVALID_JSON", f"{path}: {exc}")
    _validate_staging_value(value, context=str(path))
    return raw, value


def _repo_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(_REPOSITORY).as_posix()
    except ValueError:
        # External test inputs still receive a deterministic repo-relative label.
        digest = _sha256_bytes(str(resolved).encode("utf-8", "strict"))[:16]
        return f"external/{digest}/{resolved.name}"


def _source_row(path: Path, raw: bytes | None = None) -> dict[str, Any]:
    if raw is None:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            _fail("SOURCE_READ_ERROR", f"cannot read source {path}: {exc}")
    return {
        "path": _repo_relative(path),
        "sha256": _sha256_bytes(raw),
        "byte_count": len(raw),
    }


def _source_rows(paths: Sequence[Path]) -> list[dict[str, Any]]:
    rows = [_source_row(path) for path in paths]
    rows.sort(key=lambda row: row["path"].encode("utf-8", "strict"))
    seen: set[str] = set()
    for row in rows:
        if row["path"] in seen:
            _fail("DUPLICATE_SOURCE", f"duplicate source path {row['path']}")
        seen.add(row["path"])
    return rows


def _atomic_file(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        _fail("ATOMIC_WRITE_ERROR", f"cannot atomically replace {path}: {exc}")
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                pass


def _atomic_directory(stage: Path, destination: Path) -> None:
    backup: Path | None = None
    try:
        if destination.exists():
            backup = destination.with_name(f".{destination.name}.previous")
            if backup.exists():
                shutil.rmtree(backup)
            os.replace(destination, backup)
        os.replace(stage, destination)
    except OSError as exc:
        if destination.exists() and destination.is_dir() and stage.exists():
            shutil.rmtree(stage)
        if backup is not None and backup.exists() and not destination.exists():
            try:
                os.replace(backup, destination)
            except OSError:
                pass
        _fail("ATOMIC_WRITE_ERROR", f"cannot atomically replace {destination}: {exc}")
    finally:
        if stage.exists():
            try:
                shutil.rmtree(stage)
            except OSError:
                pass
        if backup is not None and backup.exists():
            try:
                shutil.rmtree(backup)
            except OSError:
                pass


def _deepcopy(value: Any) -> Any:
    try:
        return copy.deepcopy(value)
    except Exception as exc:
        _fail("NONCANONICAL_VALUE", f"cannot copy canonical value: {exc}")
    raise AssertionError("unreachable")


def _pointer(*tokens: str) -> str:
    return "/" + "/".join(token.replace("~", "~0").replace("/", "~1") for token in tokens)


def _unpointer(pointer: Any) -> list[str]:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        _fail("MUTATION_POINTER_INVALID", "mutation path must be an RFC6901 pointer")
    return [token.replace("~1", "/").replace("~0", "~") for token in pointer[1:].split("/")]


def _descriptor_accepts_null(descriptor: Mapping[str, Any]) -> bool:
    if descriptor.get("const", object()) is None:
        return True
    if descriptor.get("type") in {"null", "nullable-sha256", "canonical-value"}:
        return True
    alternatives = descriptor.get("one_of")
    return isinstance(alternatives, list) and any(
        isinstance(item, Mapping) and _descriptor_accepts_null(item) for item in alternatives
    )


def _normalise_schema_document(document: Any, *, schema: str, context: str) -> dict[str, Any]:
    if not isinstance(document, Mapping):
        _fail("SCHEMA_DOCUMENT_FIELDS", f"{context} schema document must be an object")
    unknown = set(document) - _DOC_ALLOWED_KEYS
    if unknown:
        _fail("SCHEMA_DOCUMENT_FIELDS", f"{context} schema document has extra fields {sorted(unknown)!r}")
    if not _DOC_REQUIRED_KEYS <= set(document):
        _fail("SCHEMA_DOCUMENT_FIELDS", f"{context} schema document omits required root fields")
    if document.get("schema", PROFILE_SCHEMA_DOCUMENT_SCHEMA) != PROFILE_SCHEMA_DOCUMENT_SCHEMA:
        _fail("SCHEMA_DOCUMENT_SCHEMA", f"{context} schema document has the wrong schema")
    if document.get("object_schema", schema) != schema:
        _fail("SCHEMA_DOCUMENT_TARGET", f"{context} schema document targets another schema")
    if document.get("type", "object") != "object":
        _fail("DESCRIPTOR_TYPE_INVALID", f"{context} schema document root must be an object")
    if document.get("additional_properties", False) is not False:
        _fail("DESCRIPTOR_CLOSURE", f"{context} schema document must reject additional properties")
    result = _deepcopy(dict(document))
    definitions = result.get("definitions", {})
    if not isinstance(definitions, Mapping):
        _fail("DESCRIPTOR_REFERENCE_INVALID", f"{context} definitions must be an object")
    properties = result["properties"]
    if not isinstance(properties, Mapping):
        _fail("DESCRIPTOR_TYPE_INVALID", f"{context}/properties must be an object")
    result["properties"] = {
        name: _resolve_descriptor(value, definitions, context=f"{context}/properties/{name}")
        for name, value in properties.items()
    }
    required = result["required_keys"]
    if not isinstance(required, list):
        _fail("DESCRIPTOR_TYPE_INVALID", f"{context}/required_keys must be an array")
    result["optional_keys"] = sorted(
        (name for name in result["properties"] if name not in set(required)),
        key=lambda name: name.encode("utf-8", "strict"),
    )
    nullable = set(result.get("nullable_keys", []))
    nullable.update(name for name, value in result["properties"].items() if _descriptor_accepts_null(value))
    result["nullable_keys"] = sorted(nullable, key=lambda name: name.encode("utf-8", "strict"))
    result.pop("definitions", None)
    result["schema"] = PROFILE_SCHEMA_DOCUMENT_SCHEMA
    result["object_schema"] = schema
    return result


def _resolve_descriptor(
    descriptor: Any,
    definitions: Mapping[str, Any],
    *,
    context: str,
    stack: tuple[str, ...] = (),
) -> Any:
    if not isinstance(descriptor, Mapping):
        _fail("DESCRIPTOR_TYPE_INVALID", f"{context} must be an object")
    if "$ref" in descriptor:
        if set(descriptor) != {"$ref"}:
            _fail("DESCRIPTOR_FIELDS_INVALID", f"{context} reference has extra fields")
        reference = descriptor["$ref"]
        if isinstance(reference, str) and reference.startswith("#/definitions/"):
            reference = reference.removeprefix("#/definitions/")
        if not isinstance(reference, str) or not reference or reference not in definitions:
            _fail("DESCRIPTOR_REFERENCE_INVALID", f"{context} has an unknown definition reference")
        if reference in stack:
            _fail("DESCRIPTOR_REFERENCE_INVALID", f"{context} has a recursive definition reference")
        return _resolve_descriptor(
            definitions[reference],
            definitions,
            context=f"{context}/$ref:{reference}",
            stack=(*stack, reference),
        )
    if "one_of" in descriptor:
        if set(descriptor) != {"one_of"}:
            _fail("DESCRIPTOR_FIELDS_INVALID", f"{context} union has extra fields")
        alternatives = descriptor["one_of"]
        if not isinstance(alternatives, list) or not alternatives:
            _fail("DESCRIPTOR_TYPE_INVALID", f"{context}/one_of must be a nonempty array")
        return {
            "one_of": [
                _resolve_descriptor(item, definitions, context=f"{context}/one_of/{index}", stack=stack)
                for index, item in enumerate(alternatives)
            ]
        }
    if "const" in descriptor and "type" not in descriptor:
        if set(descriptor) != {"const"}:
            _fail("DESCRIPTOR_FIELDS_INVALID", f"{context} constant has extra fields")
        return _deepcopy(dict(descriptor))
    result = _deepcopy(dict(descriptor))
    if result.get("type") == "object":
        properties = result.get("properties")
        if isinstance(properties, Mapping):
            result["properties"] = {
                name: _resolve_descriptor(value, definitions, context=f"{context}/properties/{name}", stack=stack)
                for name, value in properties.items()
            }
            required = result.get("required_keys", [])
            if isinstance(required, list):
                result["optional_keys"] = sorted(
                    (name for name in result["properties"] if name not in set(required)),
                    key=lambda name: name.encode("utf-8", "strict"),
                )
            nullable = set(result.get("nullable_keys", []))
            nullable.update(name for name, value in result["properties"].items() if _descriptor_accepts_null(value))
            result["nullable_keys"] = sorted(nullable, key=lambda name: name.encode("utf-8", "strict"))
        result.pop("definitions", None)
    elif result.get("type") == "array":
        if "items" in result:
            result["items"] = _resolve_descriptor(result["items"], definitions, context=f"{context}/items", stack=stack)
        if "tuple_items" in result:
            rows = result["tuple_items"]
            if isinstance(rows, list):
                result["tuple_items"] = [
                    _resolve_descriptor(value, definitions, context=f"{context}/tuple_items/{index}", stack=stack)
                    for index, value in enumerate(rows)
                ]
    return result


def _object_descriptor_fields(
    value: Mapping[str, Any],
    *,
    context: str,
) -> tuple[list[str], list[str], list[str], dict[str, Any]]:
    allowed = {
        "type",
        "required_keys",
        "optional_keys",
        "nullable_keys",
        "properties",
        "additional_properties",
        "invariants",
        "rules",
        "consumed_semantic_subhashes",
    }
    unknown = set(value) - allowed
    if unknown:
        _fail("DESCRIPTOR_FIELDS_INVALID", f"{context} object descriptor has extra fields {sorted(unknown)!r}")
    if value.get("type") != "object":
        _fail("DESCRIPTOR_TYPE_INVALID", f"{context} object descriptor has the wrong type")
    if value.get("additional_properties", False) is not False:
        _fail("DESCRIPTOR_CLOSURE", f"{context} permits additional properties")
    properties = value.get("properties")
    if not isinstance(properties, Mapping) or any(not isinstance(key, str) or not key for key in properties):
        _fail("DESCRIPTOR_TYPE_INVALID", f"{context}/properties must be an object")
    required = value.get("required_keys", [])
    if not isinstance(required, list) or any(not isinstance(item, str) or not item for item in required):
        _fail("DESCRIPTOR_TYPE_INVALID", f"{context}/required_keys must be a string array")
    optional = value.get("optional_keys")
    if optional is None:
        optional = [name for name in properties if name not in set(required)]
    nullable = value.get("nullable_keys", [])
    for name, rows in (("required_keys", required), ("optional_keys", optional), ("nullable_keys", nullable)):
        if not isinstance(rows, list) or any(not isinstance(item, str) or not item for item in rows):
            _fail("DESCRIPTOR_TYPE_INVALID", f"{context}/{name} must be a string array")
        if len(rows) != len(set(rows)):
            _fail("DESCRIPTOR_DUPLICATE_KEY", f"{context}/{name} contains duplicate names")
    if set(required) & set(optional):
        _fail("DESCRIPTOR_OVERLAP", f"{context} required and optional fields overlap")
    known = set(required) | set(optional)
    if set(properties) != known:
        _fail("DESCRIPTOR_CLOSURE", f"{context} properties do not equal required union optional")
    if not set(nullable) <= known:
        _fail("DESCRIPTOR_NULLABLE_INVALID", f"{context} nullable fields are not declared properties")
    return list(required), list(optional), list(nullable), dict(properties)


def _validate_descriptor(
    value: Any,
    *,
    context: str,
    max_encoded_bytes: int,
    max_fanout: int,
    depth: int = 0,
) -> None:
    if depth > MAX_CANONICAL_DEPTH:
        _fail("DESCRIPTOR_DEPTH", f"{context} exceeds the canonical descriptor depth")
    if not isinstance(value, Mapping):
        _fail("DESCRIPTOR_TYPE_INVALID", f"{context} must be an object")
    if "one_of" in value:
        if set(value) != {"one_of"}:
            _fail("DESCRIPTOR_FIELDS_INVALID", f"{context} union has extra fields")
        alternatives = value["one_of"]
        if not isinstance(alternatives, list) or not alternatives or len(alternatives) > max_fanout:
            _fail("DESCRIPTOR_RANGE_INVALID", f"{context}/one_of has invalid bounds")
        for index, alternative in enumerate(alternatives):
            _validate_descriptor(
                alternative,
                context=f"{context}/one_of/{index}",
                max_encoded_bytes=max_encoded_bytes,
                max_fanout=max_fanout,
                depth=depth + 1,
            )
        return
    if "const" in value and "type" not in value:
        if set(value) != {"const"}:
            _fail("DESCRIPTOR_FIELDS_INVALID", f"{context} constant has extra fields")
        _validate_staging_value(value["const"], context=f"{context}/const")
        return
    kind = value.get("type")
    if kind == "string":
        allowed = {
            "type",
            "format",
            "enum",
            "const",
            "pattern",
            "min_length",
            "max_length",
            "min_bytes",
            "max_bytes",
            "max_decoded_bytes",
            "charset",
        }
        if not set(value) <= allowed:
            _fail("DESCRIPTOR_FIELDS_INVALID", f"{context} string descriptor has extra fields")
        format_name = value.get("format")
        if format_name not in {
            None,
            "sha256",
            "finite-bits",
            "finite-f64",
            "finite-f64-bits",
            "finite_bits",
            "base64",
            "identifier-v1",
        }:
            _fail("DESCRIPTOR_FORMAT_INVALID", f"{context} has an unsupported string format")
        enum = value.get("enum")
        if enum is not None:
            if not isinstance(enum, list) or not enum or any(not isinstance(item, str) for item in enum):
                _fail("DESCRIPTOR_ENUM_INVALID", f"{context}/enum must be a nonempty string array")
            if len(enum) != len(set(enum)):
                _fail("DESCRIPTOR_ENUM_INVALID", f"{context}/enum contains duplicates")
        if "const" in value and not isinstance(value["const"], str):
            _fail("DESCRIPTOR_TYPE_INVALID", f"{context}/const must be a string")
        if "pattern" in value:
            if not isinstance(value["pattern"], str):
                _fail("DESCRIPTOR_TYPE_INVALID", f"{context}/pattern must be a string")
            try:
                re.compile(value["pattern"])
            except re.error as exc:
                _fail("DESCRIPTOR_PATTERN_INVALID", f"{context}/pattern is invalid: {exc}")
        for prefix in ("length", "bytes"):
            lower_name, upper_name = f"min_{prefix}", f"max_{prefix}"
            lower = _safe_int(value.get(lower_name, 0), context=f"{context}/{lower_name}", minimum=0)
            upper = _safe_int(
                value.get(upper_name, max_encoded_bytes),
                context=f"{context}/{upper_name}",
                minimum=0,
                maximum=max_encoded_bytes,
            )
            if lower > upper:
                _fail("DESCRIPTOR_RANGE_INVALID", f"{context} has inverted {prefix} bounds")
        if "max_decoded_bytes" in value:
            _safe_int(
                value["max_decoded_bytes"],
                context=f"{context}/max_decoded_bytes",
                minimum=0,
                maximum=max_encoded_bytes,
            )
        if value.get("charset") not in {None, "ascii", "utf8"}:
            _fail("DESCRIPTOR_FORMAT_INVALID", f"{context} has an unsupported charset")
        return
    if kind == "integer":
        allowed = {"type", "minimum", "maximum", "const", "enum"}
        if not set(value) <= allowed:
            _fail("DESCRIPTOR_FIELDS_INVALID", f"{context} integer descriptor has extra fields")
        lower = _safe_int(value.get("minimum", -MAX_CANONICAL_INTEGER), context=f"{context}/minimum")
        upper = _safe_int(value.get("maximum", MAX_CANONICAL_INTEGER), context=f"{context}/maximum")
        if lower > upper:
            _fail("DESCRIPTOR_RANGE_INVALID", f"{context} has inverted integer bounds")
        if "const" in value:
            _safe_int(value["const"], context=f"{context}/const", minimum=lower, maximum=upper)
        if "enum" in value:
            enum = value["enum"]
            if not isinstance(enum, list) or not enum:
                _fail("DESCRIPTOR_ENUM_INVALID", f"{context}/enum must be nonempty")
            for index, item in enumerate(enum):
                _safe_int(item, context=f"{context}/enum/{index}", minimum=lower, maximum=upper)
            if len(enum) != len(set(enum)):
                _fail("DESCRIPTOR_ENUM_INVALID", f"{context}/enum contains duplicates")
        return
    if kind == "boolean":
        if not set(value) <= {"type", "const", "enum"}:
            _fail("DESCRIPTOR_FIELDS_INVALID", f"{context} boolean descriptor has extra fields")
        if "const" in value and not isinstance(value["const"], bool):
            _fail("DESCRIPTOR_TYPE_INVALID", f"{context}/const must be boolean")
        if "enum" in value:
            enum = value["enum"]
            if not isinstance(enum, list) or not enum or any(not isinstance(item, bool) for item in enum):
                _fail("DESCRIPTOR_ENUM_INVALID", f"{context}/enum must be a nonempty boolean array")
        return
    if kind in {"null", "nullable-sha256", "canonical-object", "canonical-value"}:
        if set(value) != {"type"}:
            _fail("DESCRIPTOR_FIELDS_INVALID", f"{context} {kind} descriptor has extra fields")
        return
    if kind == "finite-f64-bits":
        if not set(value) <= {"type", "pattern"}:
            _fail("DESCRIPTOR_FIELDS_INVALID", f"{context} finite-f64-bits descriptor has extra fields")
        return
    if kind == "object":
        required, optional, nullable, properties = _object_descriptor_fields(value, context=context)
        del required, optional, nullable
        for name, child in properties.items():
            _validate_descriptor(
                child,
                context=f"{context}/properties/{name}",
                max_encoded_bytes=max_encoded_bytes,
                max_fanout=max_fanout,
                depth=depth + 1,
            )
        return
    if kind == "array":
        allowed = {"type", "min_items", "max_items", "items", "tuple_items", "ordered_name_enum"}
        if not set(value) <= allowed:
            _fail("DESCRIPTOR_FIELDS_INVALID", f"{context} array descriptor has extra fields")
        if ("items" in value) == ("tuple_items" in value):
            _fail("DESCRIPTOR_FIELDS_INVALID", f"{context} array must declare exactly one item form")
        lower = _safe_int(value.get("min_items", 0), context=f"{context}/min_items", minimum=0)
        upper = _safe_int(
            value.get("max_items", max_fanout),
            context=f"{context}/max_items",
            minimum=0,
            maximum=min(max_fanout, max_encoded_bytes),
        )
        if lower > upper:
            _fail("DESCRIPTOR_RANGE_INVALID", f"{context} has invalid array bounds")
        if "items" in value:
            _validate_descriptor(
                value["items"],
                context=f"{context}/items",
                max_encoded_bytes=max_encoded_bytes,
                max_fanout=max_fanout,
                depth=depth + 1,
            )
        else:
            rows = value["tuple_items"]
            if not isinstance(rows, list) or not lower <= len(rows) <= upper:
                _fail("DESCRIPTOR_RANGE_INVALID", f"{context}/tuple_items violates array bounds")
            for index, child in enumerate(rows):
                _validate_descriptor(
                    child,
                    context=f"{context}/tuple_items/{index}",
                    max_encoded_bytes=max_encoded_bytes,
                    max_fanout=max_fanout,
                    depth=depth + 1,
                )
        ordered = value.get("ordered_name_enum")
        if ordered is not None and (
            not isinstance(ordered, list)
            or any(not isinstance(item, str) for item in ordered)
            or len(ordered) != len(set(ordered))
        ):
            _fail("DESCRIPTOR_ENUM_INVALID", f"{context}/ordered_name_enum is invalid")
        return
    _fail("DESCRIPTOR_TYPE_INVALID", f"{context} uses unsupported descriptor type {kind!r}")


def _validate_scalar(value: Any, descriptor: Mapping[str, Any], *, context: str) -> None:
    if "const" in descriptor and "type" not in descriptor:
        if value != descriptor["const"] or type(value) is not type(descriptor["const"]):
            _fail("CONST_MISMATCH", f"{context} does not equal its declared constant")
        return
    kind = descriptor["type"]
    if kind in {"string", "finite-f64-bits"}:
        if not isinstance(value, str):
            _fail("TYPE_MISMATCH", f"{context} must be a string")
        if "enum" in descriptor and value not in descriptor["enum"]:
            _fail("ENUM_MISMATCH", f"{context} is outside its declared enum")
        if "const" in descriptor and value != descriptor["const"]:
            _fail("CONST_MISMATCH", f"{context} does not equal its declared constant")
        if not descriptor.get("min_length", 0) <= len(value) <= descriptor.get("max_length", MAX_CANONICAL_BYTES):
            _fail("VALUE_RANGE", f"{context} string length is outside its declared bounds")
        encoded = value.encode("utf-8", "strict")
        if not descriptor.get("min_bytes", 0) <= len(encoded) <= descriptor.get("max_bytes", MAX_CANONICAL_BYTES):
            _fail("VALUE_RANGE", f"{context} string byte length is outside its declared bounds")
        if descriptor.get("charset") == "ascii":
            try:
                value.encode("ascii", "strict")
            except UnicodeEncodeError:
                _fail("FORMAT_MISMATCH", f"{context} is not ASCII")
        pattern = descriptor.get("pattern")
        if pattern is not None and re.fullmatch(pattern, value) is None:
            _fail("FORMAT_MISMATCH", f"{context} does not match its declared pattern")
        format_name = descriptor.get("format")
        if format_name == "sha256":
            _sha(value, context=context)
        elif kind == "finite-f64-bits" or format_name in {"finite-bits", "finite-f64", "finite-f64-bits", "finite_bits"}:
            if _FINITE_BITS_RE.fullmatch(value) is None:
                _fail("FORMAT_MISMATCH", f"{context} is not finite-bit encoded")
        elif format_name == "base64":
            try:
                decoded = base64.b64decode(value, validate=True)
            except Exception:
                _fail("FORMAT_MISMATCH", f"{context} is not canonical base64")
            if len(decoded) > descriptor.get("max_decoded_bytes", MAX_CANONICAL_BYTES):
                _fail("VALUE_RANGE", f"{context} decoded bytes exceed their declared bound")
        return
    if kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            _fail("TYPE_MISMATCH", f"{context} must be an integer")
        _safe_int(
            value,
            context=context,
            minimum=descriptor.get("minimum", -MAX_CANONICAL_INTEGER),
            maximum=descriptor.get("maximum", MAX_CANONICAL_INTEGER),
        )
        if "enum" in descriptor and value not in descriptor["enum"]:
            _fail("ENUM_MISMATCH", f"{context} is outside its declared enum")
        if "const" in descriptor and value != descriptor["const"]:
            _fail("CONST_MISMATCH", f"{context} does not equal its declared constant")
        return
    if kind == "boolean":
        if not isinstance(value, bool):
            _fail("TYPE_MISMATCH", f"{context} must be a boolean")
        if "enum" in descriptor and value not in descriptor["enum"]:
            _fail("ENUM_MISMATCH", f"{context} is outside its declared enum")
        if "const" in descriptor and value != descriptor["const"]:
            _fail("CONST_MISMATCH", f"{context} does not equal its declared constant")
        return
    if kind == "null":
        if value is not None:
            _fail("TYPE_MISMATCH", f"{context} must be null")
        return
    if kind == "nullable-sha256":
        if value is not None:
            _sha(value, context=context)
        return
    _fail("TYPE_MISMATCH", f"{context} has unsupported scalar descriptor {kind!r}")


def _validate_value(
    value: Any,
    descriptor: Mapping[str, Any],
    *,
    context: str,
    max_fanout: int,
    mode: str | None = None,
    depth: int = 0,
) -> None:
    if depth > MAX_CANONICAL_DEPTH:
        _fail("FIXTURE_DEPTH", f"{context} exceeds canonical depth")
    if "one_of" in descriptor:
        accepted = 0
        for alternative in descriptor["one_of"]:
            try:
                _validate_value(
                    value,
                    alternative,
                    context=context,
                    max_fanout=max_fanout,
                    mode=mode,
                    depth=depth + 1,
                )
            except WorkflowError:
                continue
            accepted += 1
        if accepted != 1:
            _fail("TYPE_MISMATCH", f"{context} does not match exactly one union alternative")
        return
    kind = descriptor.get("type")
    if "const" in descriptor and kind is None:
        _validate_scalar(value, descriptor, context=context)
        return
    if kind in {"string", "integer", "boolean", "null", "nullable-sha256", "finite-f64-bits"}:
        _validate_scalar(value, descriptor, context=context)
        return
    if kind == "canonical-object":
        if not isinstance(value, Mapping):
            _fail("TYPE_MISMATCH", f"{context} must be an object")
        _validate_staging_value(value, context=context)
        return
    if kind == "canonical-value":
        _validate_staging_value(value, context=context)
        return
    if kind == "object":
        if not isinstance(value, Mapping):
            _fail("TYPE_MISMATCH", f"{context} must be an object")
        required, optional, nullable, properties = _object_descriptor_fields(descriptor, context=f"{context}/descriptor")
        actual = set(value)
        unknown = actual - set(properties)
        missing = set(required) - actual
        if unknown:
            _fail("EXTRA_KEY", f"{context} has undeclared fields")
        if missing:
            _fail("MISSING_REQUIRED_KEY", f"{context} omits required fields")
        if mode == "minimal_valid" and actual != set(required):
            _fail("PARTIAL_FIXTURE", f"{context} is not recursively minimal")
        if mode in {"maximal_valid", "nullable_valid"} and actual != set(required) | set(optional):
            _fail("PARTIAL_FIXTURE", f"{context} is not recursively complete")
        for name in actual:
            child = value[name]
            if child is None:
                if name not in nullable:
                    _fail("NULLABILITY_MISMATCH", f"{context}/{name} is not nullable")
            else:
                _validate_value(
                    child,
                    properties[name],
                    context=f"{context}/{name}",
                    max_fanout=max_fanout,
                    mode=mode,
                    depth=depth + 1,
                )
        return
    if kind == "array":
        if not isinstance(value, list):
            _fail("TYPE_MISMATCH", f"{context} must be an array")
        lower = descriptor.get("min_items", 0)
        upper = descriptor.get("max_items", max_fanout)
        if not lower <= len(value) <= upper or len(value) > max_fanout:
            _fail("VALUE_RANGE", f"{context} array length is outside its declared bounds")
        if "tuple_items" in descriptor:
            if len(value) != len(descriptor["tuple_items"]):
                _fail("VALUE_RANGE", f"{context} tuple length is invalid")
            rows = zip(value, descriptor["tuple_items"], strict=True)
        else:
            rows = ((child, descriptor["items"]) for child in value)
        for index, (child, child_descriptor) in enumerate(rows):
            _validate_value(
                child,
                child_descriptor,
                context=f"{context}/{index}",
                max_fanout=max_fanout,
                mode=mode,
                depth=depth + 1,
            )
        ordered = descriptor.get("ordered_name_enum")
        if ordered is not None:
            names = [item.get("name") if isinstance(item, Mapping) else None for item in value]
            expected_subset = [name for name in ordered if name in names]
            if len(names) != len(set(names)) or any(name not in ordered for name in names) or names != expected_subset:
                _fail("PARENT_ORDER_MISMATCH", f"{context} ordered names differ")
        return
    _fail("TYPE_MISMATCH", f"{context} has unsupported descriptor type")


def _root_contract(
    document: Mapping[str, Any],
    *,
    max_encoded_bytes: int,
    max_fanout: int,
) -> tuple[list[str], list[str], list[str], dict[str, Any]]:
    if not isinstance(document, Mapping):
        _fail("SCHEMA_DOCUMENT_FIELDS", "schema document must be an object")
    unknown = set(document) - _DOC_ALLOWED_KEYS
    if unknown or not _DOC_REQUIRED_KEYS <= set(document):
        _fail("SCHEMA_DOCUMENT_FIELDS", "schema document has missing or extra fields")
    if document.get("schema") != PROFILE_SCHEMA_DOCUMENT_SCHEMA:
        _fail("SCHEMA_DOCUMENT_SCHEMA", "schema document has the wrong schema")
    definitions = document.get("definitions", {})
    if not isinstance(definitions, Mapping) or any(not isinstance(name, str) or not name for name in definitions):
        _fail("DESCRIPTOR_REFERENCE_INVALID", "schema document definitions must be an object")
    properties = document["properties"]
    if not isinstance(properties, Mapping):
        _fail("DESCRIPTOR_TYPE_INVALID", "schema_document/properties must be an object")
    resolved_properties = {
        name: _resolve_descriptor(
            descriptor,
            definitions,
            context=f"schema_document/properties/{name}",
        )
        for name, descriptor in properties.items()
    }
    root_descriptor = {
        "type": "object",
        "required_keys": document["required_keys"],
        "optional_keys": document.get(
            "optional_keys",
            [name for name in resolved_properties if name not in set(document["required_keys"])],
        ),
        "nullable_keys": document.get("nullable_keys", []),
        "properties": resolved_properties,
    }
    required, optional, nullable, resolved_properties = _object_descriptor_fields(
        root_descriptor,
        context="schema_document",
    )
    for name, descriptor in resolved_properties.items():
        _validate_descriptor(
            descriptor,
            context=f"schema_document/properties/{name}",
            max_encoded_bytes=max_encoded_bytes,
            max_fanout=max_fanout,
        )
    return required, optional, nullable, resolved_properties


def _descriptor_fanout(descriptor: Mapping[str, Any]) -> int:
    if "one_of" in descriptor:
        return max(len(descriptor["one_of"]), *(_descriptor_fanout(item) for item in descriptor["one_of"]))
    kind = descriptor.get("type")
    if kind == "object":
        properties = descriptor.get("properties", {})
        return max(len(properties), *(_descriptor_fanout(item) for item in properties.values()), 0)
    if kind == "array":
        own = descriptor.get("max_items", len(descriptor.get("tuple_items", [])))
        if "items" in descriptor:
            return max(own, _descriptor_fanout(descriptor["items"]))
        return max(own, *(_descriptor_fanout(item) for item in descriptor.get("tuple_items", [])), 0)
    return 0


def _fixture_shape(
    fixture: Any,
    *,
    required: Sequence[str],
    optional: Sequence[str],
    nullable: Sequence[str],
    properties: Mapping[str, Any],
    max_fanout: int,
    context: str,
    mode: str,
) -> dict[str, Any]:
    if not isinstance(fixture, Mapping):
        _fail("PARTIAL_FIXTURE", f"{context} must be a complete object")
    result = _deepcopy(dict(fixture))
    actual = set(result)
    known = set(required) | set(optional)
    unknown = actual - known
    missing = set(required) - actual
    if unknown:
        _fail("EXTRA_KEY", f"{context} has undeclared fixture fields")
    if missing:
        _fail("MISSING_REQUIRED_KEY", f"{context} omits required fields")
    if mode == "minimal_valid" and actual != set(required):
        _fail("PARTIAL_FIXTURE", f"{context} is not the exact minimal fixture")
    if mode in {"maximal_valid", "nullable_valid"} and actual != known:
        _fail("PARTIAL_FIXTURE", f"{context} is not a complete fixture")
    for name in actual:
        child = result[name]
        if child is None:
            if name not in nullable:
                _fail("NULLABILITY_MISMATCH", f"{context}/{name} is not nullable")
        else:
            _validate_value(
                child,
                properties[name],
                context=f"{context}/{name}",
                max_fanout=max_fanout,
                mode=None,
            )
    return result


def _fixture_null_keys(fixture: Mapping[str, Any], nullable: Sequence[str]) -> list[str]:
    return [name for name in nullable if fixture.get(name) is None]


def _parent_order_check(fixture: Mapping[str, Any], parent_names: Sequence[str], *, context: str) -> None:
    expected = list(parent_names)
    if "consumed_semantic_subhashes" in fixture:
        rows = fixture["consumed_semantic_subhashes"]
        if isinstance(rows, list) and all(isinstance(row, Mapping) and isinstance(row.get("name"), str) for row in rows):
            observed = [str(row["name"]) for row in rows]
            if observed != expected:
                _fail("PARENT_ORDER_MISMATCH", f"{context} consumed parent order differs")
    if "semantic_parent_names" in fixture:
        names = fixture["semantic_parent_names"]
        if isinstance(names, list) and names != expected:
            _fail("PARENT_ORDER_MISMATCH", f"{context} parent order differs")


def _self_hash_fixture(fixture: Mapping[str, Any], *, field: str, domain: str) -> str:
    body = dict(fixture)
    body.pop(field, None)
    try:
        return canonical_hash(body, domain)
    except Exception as exc:
        _fail("SELF_HASH_INVALID", f"cannot hash fixture: {exc}")
    raise AssertionError("unreachable")


def _normalise_parent_fields(fixture: Any, parent_names: Sequence[str]) -> Any:
    if not isinstance(fixture, Mapping):
        return fixture
    result = _deepcopy(dict(fixture))
    if isinstance(result.get("consumed_semantic_subhashes"), list):
        existing = {
            row.get("name"): row.get("sha256")
            for row in result["consumed_semantic_subhashes"]
            if isinstance(row, Mapping)
        }
        result["consumed_semantic_subhashes"] = [
            {
                "name": name,
                "sha256": existing.get(name)
                if isinstance(existing.get(name), str) and _SHA256_RE.fullmatch(existing[name])
                else hashlib.sha256(name.encode("utf-8", "strict")).hexdigest(),
            }
            for name in parent_names
        ]
    if isinstance(result.get("semantic_parent_names"), list):
        result["semantic_parent_names"] = list(parent_names)
    return result


def _validate_fixture(
    fixture: Any,
    *,
    required: Sequence[str],
    optional: Sequence[str],
    nullable: Sequence[str],
    properties: Mapping[str, Any],
    max_encoded_bytes: int,
    max_fanout: int,
    self_hash_field: str,
    hash_domain: str,
    parent_names: Sequence[str],
    context: str,
    mode: str,
    recompute_self: bool,
) -> dict[str, Any]:
    if self_hash_field not in set(required) | set(optional):
        _fail("SELF_HASH_FIELD_INVALID", f"{context} self hash field is not declared")
    fixture = _normalise_parent_fields(fixture, parent_names) if recompute_self else fixture
    result = _fixture_shape(
        fixture,
        required=required,
        optional=optional,
        nullable=nullable,
        properties=properties,
        max_fanout=max_fanout,
        context=context,
        mode=mode,
    )
    if result.get(self_hash_field) is None:
        _fail("NULLABILITY_MISMATCH", f"{context}/{self_hash_field} cannot be null")
    _parent_order_check(result, parent_names, context=context)
    expected = _self_hash_fixture(result, field=self_hash_field, domain=hash_domain)
    if recompute_self:
        result[self_hash_field] = expected
        _validate_value(result[self_hash_field], properties[self_hash_field], context=f"{context}/{self_hash_field}", max_fanout=max_fanout)
    elif result.get(self_hash_field) != expected:
        _fail("SELF_HASH_MISMATCH", f"{context} self hash does not match its hash domain")
    if len(_canonical(result, context=context)) > max_encoded_bytes:
        _fail("FIXTURE_OVER_BUDGET", f"{context} exceeds max_encoded_bytes")
    return result


def _bad_value(descriptor: Mapping[str, Any]) -> Any:
    if "one_of" in descriptor:
        return {"__cassi_invalid__": True}
    kind = descriptor.get("type")
    if kind == "string":
        return 0
    if kind == "integer":
        return "not-an-integer"
    if kind == "boolean":
        return 0
    if kind in {"null", "nullable-sha256"}:
        return 0
    if kind == "object":
        return []
    if kind == "array":
        return {}
    return 0


def _mutation_delete(value: Any, tokens: Sequence[str]) -> None:
    if not tokens:
        _fail("MUTATION_POINTER_INVALID", "root deletion is not supported")
    parent = value
    for token in tokens[:-1]:
        if isinstance(parent, Mapping):
            if token not in parent:
                _fail("MUTATION_POINTER_INVALID", "mutation path is absent")
            parent = parent[token]
        elif isinstance(parent, list):
            if not token.isdigit() or int(token) >= len(parent):
                _fail("MUTATION_POINTER_INVALID", "mutation array path is absent")
            parent = parent[int(token)]
        else:
            _fail("MUTATION_POINTER_INVALID", "mutation path descends through a scalar")
    last = tokens[-1]
    if isinstance(parent, dict):
        if last not in parent:
            _fail("MUTATION_POINTER_INVALID", "mutation path is absent")
        del parent[last]
    elif isinstance(parent, list):
        if not last.isdigit() or int(last) >= len(parent):
            _fail("MUTATION_POINTER_INVALID", "mutation array path is absent")
        del parent[int(last)]
    else:
        _fail("MUTATION_POINTER_INVALID", "mutation parent is not a container")


def _mutation_set(value: Any, tokens: Sequence[str], replacement: Any, *, insert: bool) -> None:
    if not tokens:
        _fail("MUTATION_POINTER_INVALID", "root replacement is not supported")
    parent = value
    for token in tokens[:-1]:
        if isinstance(parent, Mapping):
            if token not in parent:
                _fail("MUTATION_POINTER_INVALID", "mutation path is absent")
            parent = parent[token]
        elif isinstance(parent, list):
            if not token.isdigit() or int(token) >= len(parent):
                _fail("MUTATION_POINTER_INVALID", "mutation array path is absent")
            parent = parent[int(token)]
        else:
            _fail("MUTATION_POINTER_INVALID", "mutation path descends through a scalar")
    last = tokens[-1]
    if isinstance(parent, dict):
        if insert and last in parent:
            _fail("MUTATION_POINTER_INVALID", "insert path already exists")
        if not insert and last not in parent:
            _fail("MUTATION_POINTER_INVALID", "replace path is absent")
        parent[last] = _deepcopy(replacement)
    elif isinstance(parent, list):
        if insert and last == "-":
            parent.append(_deepcopy(replacement))
            return
        if not last.isdigit():
            _fail("MUTATION_POINTER_INVALID", "mutation array index is invalid")
        index = int(last)
        if insert:
            if index > len(parent):
                _fail("MUTATION_POINTER_INVALID", "insert array index is absent")
            parent.insert(index, _deepcopy(replacement))
        else:
            if index >= len(parent):
                _fail("MUTATION_POINTER_INVALID", "replace array index is absent")
            parent[index] = _deepcopy(replacement)
    else:
        _fail("MUTATION_POINTER_INVALID", "mutation parent is not a container")


def _apply_mutation(value: Any, mutation: Any) -> Any:
    if not isinstance(mutation, Mapping):
        _fail("MUTATION_INVALID", "mutation must be an object")
    operation = mutation.get("op")
    if operation not in {"delete", "insert", "replace"}:
        _fail("MUTATION_INVALID", "mutation operation is not delete, insert, or replace")
    allowed = {"op", "path"} if operation == "delete" else {"op", "path", "value"}
    if set(mutation) != allowed:
        _fail("MUTATION_INVALID", "mutation has missing or extra fields")
    result = _deepcopy(value)
    tokens = _unpointer(mutation["path"])
    if operation == "delete":
        _mutation_delete(result, tokens)
    else:
        _mutation_set(result, tokens, mutation["value"], insert=operation == "insert")
    return result


def _normalise_parents(value: Any, *, context: str) -> list[str]:
    if value is None:
        _fail("PARENT_TYPE_INVALID", f"{context} must be a string array")
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        _fail("PARENT_TYPE_INVALID", f"{context} must be a string array")
    if len(value) != len(set(value)):
        _fail("PARENT_DUPLICATE", f"{context} contains duplicate parents")
    if any(item not in _PARENT_INDEX for item in value):
        _fail("PARENT_UNKNOWN", f"{context} contains an unknown semantic parent")
    if value != sorted(value, key=_PARENT_INDEX.__getitem__):
        _fail("PARENT_ORDER_MISMATCH", f"{context} is not in canonical parent order")
    return list(value)


def _known_schema_class(schema: str) -> str | None:
    return _SCHEMA_CLASSIFICATION.get(schema)




def _entry_value(payload: Mapping[str, Any], primary: str, aliases: Sequence[str], *, context: str) -> Any:
    present = [name for name in (primary, *aliases) if name in payload]
    if len(present) > 1:
        _fail("ENTRY_DUPLICATE_FIELD", f"{context} supplies aliases for {primary}")
    return payload[present[0]] if present else None


def _fixture_set_input(payload: Mapping[str, Any], *, context: str) -> Any:
    direct = payload.get("canonical_fixture_set")
    if direct is not None:
        if any(name in payload for name in ("fixture", "fixtures")):
            _fail("ENTRY_DUPLICATE_FIELD", f"{context} supplies multiple fixture forms")
        return _deepcopy(direct)
    if "fixture" in payload and "fixtures" in payload:
        _fail("ENTRY_DUPLICATE_FIELD", f"{context} supplies multiple fixture forms")
    old_fixture = payload.get("fixture")
    if old_fixture is not None:
        return {"minimal_valid": _deepcopy(old_fixture), "maximal_valid": _deepcopy(old_fixture), "nullable_valid": []}
    fixtures = payload.get("fixtures")
    if fixtures is not None:
        if isinstance(fixtures, Mapping):
            return _deepcopy(fixtures)
        if isinstance(fixtures, list) and len(fixtures) == 1:
            return {"minimal_valid": _deepcopy(fixtures[0]), "maximal_valid": _deepcopy(fixtures[0]), "nullable_valid": []}
        _fail("PARTIAL_FIXTURE", f"{context} fixtures must be a fixture-set object")
    _fail("PARTIAL_FIXTURE", f"{context} does not provide fixtures")
    raise AssertionError("unreachable")


def _generate_controls(
    *,
    schema: str,
    required: Sequence[str],
    optional: Sequence[str],
    nullable: Sequence[str],
    properties: Mapping[str, Any],
    maximal: Mapping[str, Any],
    parent_names: Sequence[str],
    self_hash_field: str,
) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []
    required_name = sorted(required, key=lambda item: item.encode("utf-8", "strict"))[0]
    controls.append(
        {
            "control_id": f"{schema}:missing-required",
            "base_fixture": "maximal_valid",
            "operation": "delete",
            "pointer": _pointer(required_name),
            "value": None,
            "expected_error": "MISSING_REQUIRED_KEY",
        }
    )
    extra_name = "__cassi_fi_extra__"
    while extra_name in set(required) | set(optional):
        extra_name += "_x"
    controls.append(
        {
            "control_id": f"{schema}:extra-key",
            "base_fixture": "minimal_valid",
            "operation": "insert",
            "pointer": _pointer(extra_name),
            "value": 0,
            "expected_error": "EXTRA_KEY",
        }
    )
    bad_hash = "0" * 64
    if maximal[self_hash_field] == bad_hash:
        bad_hash = "f" * 64
    controls.append(
        {
            "control_id": f"{schema}:self-hash-tamper",
            "base_fixture": "maximal_valid",
            "operation": "replace",
            "pointer": _pointer(self_hash_field),
            "value": bad_hash,
            "expected_error": "SELF_HASH_MISMATCH",
        }
    )
    for name in sorted(
        (item for item in nullable if item != self_hash_field),
        key=lambda item: item.encode("utf-8", "strict"),
    ):
        controls.append(
            {
                "control_id": f"{schema}:nullable-type:{name}",
                "base_fixture": "maximal_valid",
                "operation": "replace",
                "pointer": _pointer(name),
                "value": _bad_value(properties[name]),
                "expected_error": "TYPE_MISMATCH",
            }
        )
    if len(parent_names) > 1 and isinstance(maximal.get("consumed_semantic_subhashes"), list):
        rows = maximal["consumed_semantic_subhashes"]
        if len(rows) > 1 and all(isinstance(row, Mapping) and isinstance(row.get("name"), str) for row in rows):
            controls.append(
                {
                    "control_id": f"{schema}:parent-order",
                    "base_fixture": "maximal_valid",
                    "operation": "replace",
                    "pointer": _pointer("consumed_semantic_subhashes", "0", "name"),
                    "value": rows[1]["name"],
                    "expected_error": "PARENT_ORDER_MISMATCH",
                }
            )
    elif len(parent_names) > 1 and isinstance(maximal.get("semantic_parent_names"), list):
        rows = maximal["semantic_parent_names"]
        if len(rows) > 1 and all(isinstance(name, str) for name in rows):
            controls.append(
                {
                    "control_id": f"{schema}:parent-order",
                    "base_fixture": "maximal_valid",
                    "operation": "replace",
                    "pointer": _pointer("semantic_parent_names", "0"),
                    "value": rows[1],
                    "expected_error": "PARENT_ORDER_MISMATCH",
                }
            )
    controls.sort(key=lambda row: row["control_id"].encode("utf-8", "strict"))
    _canonical(controls, context=f"{schema}/mutation_controls")
    return controls


def _replay_controls(entry: Mapping[str, Any], *, context: str) -> list[dict[str, Any]]:
    required, optional, nullable, properties = _root_contract(
        entry["schema_document"],
        max_encoded_bytes=entry["max_encoded_bytes"],
        max_fanout=entry["max_fanout"],
    )
    fixtures = entry["canonical_fixture_set"]
    controls = entry["mutation_controls"]
    if not isinstance(controls, list) or not controls:
        _fail("MUTATION_CONTROLS_EMPTY", f"{context} mutation controls must be a nonempty array")
    replayed: list[dict[str, Any]] = []
    fields = {"control_id", "base_fixture", "operation", "pointer", "value", "expected_error"}
    for row in controls:
        if not isinstance(row, Mapping) or set(row) != fields:
            _fail("MUTATION_CONTROL_FIELDS", f"{context} mutation control has missing or extra fields")
        control_id = row["control_id"]
        base_name = row["base_fixture"]
        if not isinstance(control_id, str) or not control_id:
            _fail("MUTATION_CONTROL_FIELDS", f"{context} mutation control id is invalid")
        if base_name not in {"minimal_valid", "maximal_valid"}:
            _fail("MUTATION_CONTROL_FIELDS", f"{context} mutation base fixture is invalid")
        mutation = {"op": row["operation"], "path": row["pointer"]}
        if row["operation"] != "delete":
            mutation["value"] = row["value"]
        try:
            mutated = _apply_mutation(fixtures[base_name], mutation)
            _validate_fixture(
                mutated,
                required=required,
                optional=optional,
                nullable=nullable,
                properties=properties,
                max_encoded_bytes=entry["max_encoded_bytes"],
                max_fanout=entry["max_fanout"],
                self_hash_field=entry["self_hash_field"],
                hash_domain=entry["hash_domain"],
                parent_names=entry["semantic_parent_names"],
                context=f"{context}/{control_id}",
                mode="maximal_valid" if base_name == "maximal_valid" else "minimal_valid",
                recompute_self=False,
            )
        except WorkflowError as exc:
            observed = exc.code
        else:
            _fail("MUTATION_NOT_REJECTED", f"{context}/{control_id} mutation was accepted")
        expected = row["expected_error"]
        if observed != expected:
            _fail(
                "MUTATION_ERROR_CODE_MISMATCH",
                f"{context}/{control_id} observed {observed}, expected {expected}",
            )
        replayed.append({"control_id": control_id, "observed_error": observed, "status": "PASS"})
    return replayed


def _normalise_entry(payload: Mapping[str, Any], *, context: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        _fail("ENTRY_TYPE_INVALID", f"{context} must be an object")
    allowed = _ENTRY_KEY_SET | {
        "max_bytes",
        "semantic_parents",
        "fixture",
        "fixtures",
        "fixture_sha256",
        "document",
        "parents",
        "object_class_override",
        "class_override",
        "migration",
        "fixture_set_sha256",
    }
    extra = set(payload) - allowed
    if extra:
        _fail("ENTRY_EXTRA_FIELD", f"{context} has extra fields {sorted(extra)!r}")
    schema = payload.get("schema")
    if not isinstance(schema, str) or not schema or schema == "cassi.qi-flow-action-ack.v1":
        _fail("SCHEMA_FORBIDDEN", f"{context} has a forbidden or invalid schema")
    version_match = _SCHEMA_VERSION_RE.search(schema)
    if version_match is None:
        _fail("SCHEMA_VERSION_INVALID", f"{context} schema has no canonical version")
    version = _safe_int(payload.get("version", int(version_match.group(1))), context=f"{context}/version", minimum=1)
    if version != int(version_match.group(1)):
        _fail("SCHEMA_VERSION_INVALID", f"{context} version does not match schema")
    full_entry = set(payload) == _ENTRY_KEY_SET
    if not full_entry:
        lean_requirements = {
            "lifecycle": ("lifecycle",),
            "max_encoded_bytes": ("max_encoded_bytes", "max_bytes"),
            "max_fanout": ("max_fanout",),
            "semantic_parent_names": ("semantic_parent_names", "semantic_parents", "parents"),
            "hash_domain": ("hash_domain",),
            "self_hash_field": ("self_hash_field",),
        }
        missing = [
            name
            for name, aliases in lean_requirements.items()
            if not any(alias in payload for alias in aliases)
        ]
        if missing:
            _fail("ENTRY_FIELDS_INVALID", f"{context} lean entry omits metadata fields {missing!r}")
    for hash_name in (
        "schema_document_sha256",
        "canonical_fixture_set_sha256",
        "mutation_controls_sha256",
        "fixture_sha256",
        "fixture_set_sha256",
    ):
        if hash_name in payload:
            _sha(payload[hash_name], context=f"{context}/{hash_name}")
    if "mutation_controls" in payload and not isinstance(payload["mutation_controls"], list):
        _fail("NONCANONICAL_TYPE", f"{context}/mutation_controls must be an array when supplied")
    raw_document = _entry_value(payload, "schema_document", ("document",), context=context)
    if raw_document is None:
        _fail("SCHEMA_DOCUMENT_MISSING", f"{context} does not provide schema_document")
    document = _normalise_schema_document(raw_document, schema=schema, context=context)
    max_encoded_bytes_value = _entry_value(payload, "max_encoded_bytes", ("max_bytes",), context=context)
    known_class = _known_schema_class(schema)
    if known_class is None:
        _fail("OBJECT_CLASS_MISSING", f"{context} has no frozen schema classification")
    object_class = known_class


    max_encoded_bytes = _safe_int(
        max_encoded_bytes_value,
        context=f"{context}/max_encoded_bytes",
        minimum=1,
        maximum=_MAX_SCHEMA_OBJECT_BYTES,
    )
    supplied_max_fanout = _safe_int(
        payload["max_fanout"],
        context=f"{context}/max_fanout",
        minimum=0,
        maximum=max_encoded_bytes,
    )

    parents_value = _entry_value(payload, "semantic_parent_names", ("semantic_parents", "parents"), context=context)
    semantic_parent_names = _normalise_parents(parents_value, context=f"{context}/semantic_parent_names")
    lifecycle = payload["lifecycle"]
    if not (
        isinstance(lifecycle, str)
        and lifecycle
        or isinstance(lifecycle, Mapping)
        and bool(lifecycle)
    ):
        _fail("LIFECYCLE_INVALID", f"{context}/lifecycle must be a nonempty canonical value")
    _validate_staging_value(lifecycle, context=f"{context}/lifecycle")
    lifecycle = _deepcopy(lifecycle)
    self_hash_field = payload["self_hash_field"]
    if not isinstance(self_hash_field, str) or not self_hash_field:
        _fail("SELF_HASH_FIELD_INVALID", f"{context}/self_hash_field is invalid")
    hash_domain = payload["hash_domain"]
    if not isinstance(hash_domain, str) or not hash_domain:
        _fail("HASH_DOMAIN_INVALID", f"{context}/hash_domain is invalid")
    verifier = "stdlib-schema-replay-v1"
    migration = "new-schema-version-and-contract-root-v1"

    required, optional, nullable, properties = _root_contract(
        document,
        max_encoded_bytes=max_encoded_bytes,
        max_fanout=max_encoded_bytes,
    )
    max_fanout = max(
        supplied_max_fanout,
        len(properties),
        *(_descriptor_fanout(descriptor) for descriptor in properties.values()),
    )
    if document.get("object_schema") != schema:
        _fail("SCHEMA_DOCUMENT_TARGET", f"{context} schema document targets another schema")
    if not required:
        _fail("DESCRIPTOR_REQUIRED_EMPTY", f"{context} schema declares no required fields")
    if self_hash_field not in required:
        _fail("SELF_HASH_FIELD_INVALID", f"{context} self hash field must be required")
    fixture_set = _fixture_set_input(payload, context=context)
    if not isinstance(fixture_set, Mapping) or set(fixture_set) != {"minimal_valid", "maximal_valid", "nullable_valid"}:
        _fail("FIXTURE_SET_FIELDS", f"{context} fixture set must contain minimal_valid, maximal_valid, and nullable_valid")
    if self_hash_field in nullable:
        _fail("SELF_HASH_FIELD_INVALID", f"{context} self hash field cannot be nullable")
    nullable_rows = fixture_set["nullable_valid"]
    if not isinstance(nullable_rows, list):
        _fail("PARTIAL_FIXTURE", f"{context}/nullable_valid must be an array")
    minimal = _validate_fixture(
        fixture_set["minimal_valid"],
        required=required,
        optional=optional,
        nullable=nullable,
        properties=properties,
        max_encoded_bytes=max_encoded_bytes,
        max_fanout=max_fanout,
        self_hash_field=self_hash_field,
        hash_domain=hash_domain,
        parent_names=semantic_parent_names,
        context=f"{context}/minimal_valid",
        mode="minimal_valid",
        recompute_self=True,
    )
    maximal = _validate_fixture(
        fixture_set["maximal_valid"],
        required=required,
        optional=optional,
        nullable=nullable,
        properties=properties,
        max_encoded_bytes=max_encoded_bytes,
        max_fanout=max_fanout,
        self_hash_field=self_hash_field,
        hash_domain=hash_domain,
        parent_names=semantic_parent_names,
        context=f"{context}/maximal_valid",
        mode="maximal_valid",
        recompute_self=True,
    )
    nullable_valid: list[dict[str, Any]] = []
    candidate_rows = list(nullable_rows)
    candidate_rows.extend(
        {
            **_deepcopy(maximal),
            name: None,
        }
        for name in nullable
    )
    observed_nullable: set[str] = set()
    seen_fixture_hashes: set[str] = set()
    for index, fixture in enumerate(candidate_rows):
        row = _validate_fixture(
            fixture,
            required=required,
            optional=optional,
            nullable=nullable,
            properties=properties,
            max_encoded_bytes=max_encoded_bytes,
            max_fanout=max_fanout,
            self_hash_field=self_hash_field,
            hash_domain=hash_domain,
            parent_names=semantic_parent_names,
            context=f"{context}/nullable_valid/{index}",
            mode="nullable_valid",
            recompute_self=True,
        )
        null_keys = _fixture_null_keys(row, nullable)
        if not null_keys:
            continue
        observed_nullable.update(null_keys)
        row_hash = _sha256_bytes(_canonical(row, context=f"{context}/nullable_valid/{index}"))
        if row_hash not in seen_fixture_hashes:
            seen_fixture_hashes.add(row_hash)
            nullable_valid.append(row)
    if observed_nullable != set(nullable):
        _fail("PARTIAL_FIXTURE", f"{context}/nullable_valid does not cover every nullable field")
    nullable_valid.sort(key=lambda row: _canonical(row, context=f"{context}/nullable_valid-sort"))
    canonical_fixture_set = {
        "minimal_valid": minimal,
        "maximal_valid": maximal,
        "nullable_valid": nullable_valid,
    }
    mutation_controls = _generate_controls(
        schema=schema,
        required=required,
        optional=optional,
        nullable=nullable,
        properties=properties,
        maximal=maximal,
        parent_names=semantic_parent_names,
        self_hash_field=self_hash_field,
    )
    entry: dict[str, Any] = {
        "schema": schema,
        "version": version,
        "object_class": object_class,
        "lifecycle": lifecycle,
        "max_encoded_bytes": max_encoded_bytes,
        "max_fanout": max_fanout,
        "semantic_parent_names": semantic_parent_names,
        "schema_document": _deepcopy(dict(document)),
        "schema_document_sha256": canonical_hash(document, SCHEMA_DOCUMENT_HASH_DOMAIN),
        "fixture_id": payload.get("fixture_id", f"{schema}:registry-fixture"),
        "canonical_fixture_set": canonical_fixture_set,
        "canonical_fixture_set_sha256": canonical_hash(canonical_fixture_set, SCHEMA_FIXTURE_SET_HASH_DOMAIN),
        "mutation_controls": mutation_controls,
        "mutation_controls_sha256": canonical_hash(mutation_controls, SCHEMA_MUTATION_CONTROLS_HASH_DOMAIN),
        "hash_domain": hash_domain,
        "self_hash_field": self_hash_field,
        "independent_verifier": verifier,
        "migration_policy": migration,
    }
    if not isinstance(entry["fixture_id"], str) or not entry["fixture_id"]:
        _fail("FIXTURE_ID_INVALID", f"{context}/fixture_id is invalid")
    if self_hash_field not in properties or properties[self_hash_field].get("type") != "string":
        _fail("SELF_HASH_FIELD_INVALID", f"{context} self hash field must be a string property")
    _canonical(entry, context=context)
    _replay_controls(entry, context=context)
    return entry


def _expand_input(payload: Any, *, context: str) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        _fail("INPUT_MAPPING_REQUIRED", f"{context} must be a complete JSON mapping")
    if "entries" in payload:
        allowed = {"schema", "entries", "self_sha256"}
        if set(payload) - allowed:
            _fail("INPUT_FIELDS_INVALID", f"{context} registry wrapper has extra fields")
        if "self_sha256" in payload:
            wrapper_body = dict(payload)
            supplied = wrapper_body.pop("self_sha256")
            domain = wrapper_body.get("schema")
            if not isinstance(domain, str) or supplied != canonical_hash(wrapper_body, domain):
                _fail("INPUT_SELF_HASH_MISMATCH", f"{context} registry wrapper self hash mismatch")
        entries = payload["entries"]
        if not isinstance(entries, list) or any(not isinstance(item, Mapping) for item in entries):
            _fail("INPUT_MAPPING_REQUIRED", f"{context}/entries must contain mappings")
        return [dict(item) for item in entries]
    if "schema" in payload:
        return [dict(payload)]
    if payload and all(isinstance(value, Mapping) for value in payload.values()):
        result: list[Mapping[str, Any]] = []
        for schema, value in payload.items():
            if not isinstance(schema, str):
                _fail("INPUT_MAPPING_REQUIRED", f"{context} schema keys must be strings")
            row = dict(value)
            if "schema" in row and row["schema"] != schema:
                _fail("SCHEMA_KEY_MISMATCH", f"{context} mapping key does not match entry schema")
            row.setdefault("schema", schema)
            result.append(row)
        return result
    _fail("INPUT_MAPPING_REQUIRED", f"{context} is not a schema entry mapping")
    raise AssertionError("unreachable")



def _discover_schema_paths(positional: Sequence[str], options: Sequence[str] | None) -> list[Path]:
    names = list(positional) + list(options or [])
    if names:
        paths = [Path(name).resolve() for name in names]
    else:
        directory = _DIAG / "cassi-fi-schema-inputs"
        paths = sorted((path.resolve() for path in directory.glob("*.json") if path.is_file()), key=lambda path: _repo_relative(path).encode("utf-8", "strict")) if directory.is_dir() else []
    seen: set[Path] = set()
    for path in paths:
        if path in seen:
            _fail("DUPLICATE_INPUT", f"duplicate schema input {path}")
        seen.add(path)
    return paths




def _normalise_registry(paths: Sequence[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    payloads: list[tuple[Path, bytes, Any]] = []
    for path in paths:
        raw, payload = _load_json(path)
        payloads.append((path, raw, payload))
    source_rows = [_source_row(path, raw) for path, raw, _ in payloads]
    source_rows.extend(
        _source_rows(
            [
                _REPOSITORY / "cassi_qi_bootstrap.py",
                _REPOSITORY / "cassi_qi_profile.py",
            ]
        )
    )
    source_rows.sort(key=lambda row: row["path"].encode("utf-8", "strict"))
    if len({row["path"] for row in source_rows}) != len(source_rows):
        _fail("DUPLICATE_SOURCE", "schema source identities are not unique")
    if payloads:
        input_rows: list[Mapping[str, Any]] = []
        for path, _, payload in payloads:
            input_rows.extend(_expand_input(payload, context=str(path)))
    else:
        _fail(
            "NO_SCHEMA_INPUTS",
            "no schema inputs were supplied or discovered under _diag/cassi-fi-schema-inputs",
        )
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, payload in enumerate(input_rows):
        entry = _normalise_entry(payload, context=f"entry[{index}]")
        schema = entry["schema"]
        if schema in seen:
            _fail("DUPLICATE_SCHEMA", f"duplicate schema entry {schema}")
        seen.add(schema)
        entries.append(entry)
    entries.sort(key=lambda row: row["schema"].encode("utf-8", "strict"))
    expected = set(_SCHEMA_CLASSIFICATION)
    observed = {entry["schema"] for entry in entries}
    if observed != expected:
        _fail(
            "REGISTRY_INVENTORY_MISMATCH",
            "schema registry inventory mismatch: "
            f"missing={sorted(expected - observed)!r}, extra={sorted(observed - expected)!r}",
        )
    if not entries:
        _fail("REGISTRY_EMPTY", "schema registry contains no entries")
    return entries, source_rows


def _shard_body(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": _REGISTRY_SHARD_SCHEMA,
        "entries": [_deepcopy(dict(entry)) for entry in entries],
        "entry_count": len(entries),
        "first_schema": entries[0]["schema"],
        "last_schema": entries[-1]["schema"],
    }
    body["self_sha256"] = _canonical_hash_unbounded(body, _REGISTRY_SHARD_SCHEMA, context="schema registry shard")
    return body


def _build_shards(entries: Sequence[Mapping[str, Any]]) -> tuple[dict[str, bytes], list[dict[str, Any]]]:
    shards: dict[str, bytes] = {}
    rows: list[dict[str, Any]] = []
    current: list[Mapping[str, Any]] = []
    shard_index = 1
    for entry in entries:
        candidate = current + [entry]
        candidate_bytes = _canonical_unbounded(_shard_body(candidate), context="schema registry shard candidate")
        if len(candidate_bytes) > MAX_CANONICAL_BYTES and current:
            body = _shard_body(current)
            raw = _canonical(body, context="schema registry shard")
            relative = f"shards/shard-{shard_index:06d}.json"
            shards[relative] = raw
            rows.append(
                {
                    "path": relative,
                    "raw_sha256": _sha256_bytes(raw),
                    "byte_count": len(raw),
                    "entry_count": len(current),
                    "first_schema": current[0]["schema"],
                    "last_schema": current[-1]["schema"],
                }
            )
            shard_index += 1
            current = [entry]
            candidate = current
            candidate_bytes = _canonical_unbounded(_shard_body(current), context="schema registry shard candidate")
        if len(candidate_bytes) > MAX_CANONICAL_BYTES:
            _fail("SHARD_OVER_BUDGET", f"schema entry {entry['schema']} exceeds MAX_CANONICAL_BYTES")
        current = candidate
    if current:
        body = _shard_body(current)
        raw = _canonical(body, context="schema registry shard")
        relative = f"shards/shard-{shard_index:06d}.json"
        shards[relative] = raw
        rows.append(
            {
                "path": relative,
                "raw_sha256": _sha256_bytes(raw),
                "byte_count": len(raw),
                "entry_count": len(current),
                "first_schema": current[0]["schema"],
                "last_schema": current[-1]["schema"],
            }
        )
    return shards, rows


def _registry_manifest(entries: Sequence[Mapping[str, Any]], source_rows: Sequence[Mapping[str, Any]], shard_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    entry_hashes = [
        {
            "schema": entry["schema"],
            "sha256": canonical_hash(entry, SCHEMA_REGISTRY_ENTRY_HASH_DOMAIN),
        }
        for entry in entries
    ]
    body: dict[str, Any] = {
        "schema": SCHEMA_REGISTRY_SCHEMA,
        "version": 1,
        "entry_keys": list(_ENTRY_KEYS),
        "source_hashes": [_deepcopy(dict(row)) for row in source_rows],
        "shards": [_deepcopy(dict(row)) for row in shard_rows],
        "entry_hashes": entry_hashes,
        "entry_count": len(entries),
        "first_schema": entries[0]["schema"] if entries else None,
        "last_schema": entries[-1]["schema"] if entries else None,
    }
    body["self_sha256"] = canonical_hash(body, SCHEMA_REGISTRY_SCHEMA)
    return body


def _stage_registry(entries: Sequence[Mapping[str, Any]], source_rows: Sequence[Mapping[str, Any]]) -> tuple[Path, dict[str, Any]]:
    shards, shard_rows = _build_shards(entries)
    manifest = _registry_manifest(entries, source_rows, shard_rows)
    manifest_bytes = _canonical(manifest, context="schema registry manifest")
    stage = Path(tempfile.mkdtemp(prefix=".cassi-fi-schema-", dir=_DIAG))
    try:
        (stage / "shards").mkdir(parents=True, exist_ok=True)
        for relative, raw in shards.items():
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        (stage / "manifest.json").write_bytes(manifest_bytes)
    except OSError as exc:
        shutil.rmtree(stage, ignore_errors=True)
        _fail("ATOMIC_WRITE_ERROR", f"cannot stage schema registry: {exc}")
    return stage, manifest


def _status_read() -> dict[str, Any] | None:
    path = _DIAG / "cassi-fi-status.json"
    if not path.exists():
        return None
    raw, payload = _load_json(path)
    if (
        not isinstance(payload, Mapping)
        or set(payload) != {
            "schema",
            "version",
            "source_hashes",
            "current",
            "completed_gates",
            "artifact_paths",
            "invalidated_descendants",
            "self_sha256",
        }
        or payload.get("schema") != _WORKFLOW_STATUS_SCHEMA
        or payload.get("version") != 1
    ):
        _fail("STATUS_INVALID", "existing workflow status has invalid fields")
    if raw != _canonical(payload, context="workflow status"):
        _fail("STATUS_INVALID", "existing workflow status is not canonical JSON")
    supplied = payload.get("self_sha256")
    body = dict(payload)
    body.pop("self_sha256", None)
    if supplied != canonical_hash(body, _WORKFLOW_STATUS_DOMAIN):
        _fail("STATUS_INVALID", "existing workflow status self hash does not verify")
    return dict(payload)


def _manifest_identity() -> str | None:
    path = _DIAG / "cassi-fi-schema-registry" / "manifest.json"
    if not path.exists():
        return None
    _, manifest = _load_registry_entries()
    return str(manifest["self_sha256"])


def _materialized_profile_path() -> Path:
    return _PROFILE_OUTPUT if _PROFILE_OUTPUT.exists() else _DEVELOPMENT_PROFILE


def _profile_identity() -> tuple[QiFlowProfile, Any]:
    path = _materialized_profile_path()
    if not path.exists():
        profile = QiFlowProfile.from_defaults(profile_id="qi-flow-development-v1")
        root = validate_contract_root(profile.contract_root)
        return profile, root
    if path == _PROFILE_OUTPUT:
        raw, payload = _load_json(path)
        if raw != _canonical(payload, context="materialized development profile"):
            _fail("PROFILE_INVALID", "materialized development profile is not canonical JSON")
    try:
        profile = load_development_profile(path)
    except Exception as exc:
        _fail("PROFILE_INVALID", f"development profile cannot be loaded: {exc}")
    try:
        root = validate_contract_root(profile.contract_root)
        profile = validate_profile(profile)
    except Exception as exc:
        _fail("PROFILE_INVALID", f"profile/root validation failed: {exc}")
    return profile, root

def _identity_context(profile: QiFlowProfile | None = None, root: Any | None = None, *, registry_sha256: str | None = None) -> dict[str, Any]:
    if profile is None or root is None:
        profile, root = _profile_identity()
    return {
        "registry_sha256": registry_sha256 if registry_sha256 is not None else _manifest_identity(),
        "profile_sha256": profile.profile_sha256,
        "contract_root_sha256": root.sha256,
    }


def _gate_rank(gate: str) -> int:
    order = {"schemas": 0, "profile": 1, "G1": 2, "W1": 3, "W2": 4, "W3": 5, "W3N": 6}
    return order.get(gate, 100)


def _status_update(
    *,
    gate: str,
    receipt_path: Path,
    receipt_sha256: str,
    artifact_paths: Sequence[Path],
    dependency_hashes: Mapping[str, Any],
    source_rows: Sequence[Mapping[str, Any]],
    identities: Mapping[str, Any],
) -> dict[str, Any]:
    old = _status_read()
    old_completed = list(old.get("completed_gates", [])) if old else []
    old_invalidated = list(old.get("invalidated_descendants", [])) if old else []
    old_current = dict(old.get("current", {})) if old else {}
    changed = {
        key
        for key, value in identities.items()
        if old_current.get(key) != value
    }
    completed: list[dict[str, Any]] = []
    invalidated = list(old_invalidated)
    current_rank = _gate_rank(gate)
    prior_current = next(
        (
            row
            for row in old_completed
            if isinstance(row, Mapping) and row.get("gate") == gate
        ),
        None,
    )
    gate_changed = bool(
        prior_current
        and (
            prior_current.get("receipt_sha256") != receipt_sha256
            or prior_current.get("dependency_hashes") != dependency_hashes
        )
    )
    for row in old_completed:
        if not isinstance(row, Mapping) or not isinstance(row.get("gate"), str):
            _fail("STATUS_INVALID", "existing status completed gate row is invalid")
        prior_gate = str(row["gate"])
        prior_deps = row.get("dependency_hashes", {})
        same_gate = prior_gate == gate
        invalidate = same_gate and gate_changed
        if not same_gate and _gate_rank(prior_gate) > current_rank and (gate_changed or bool(changed)):
            invalidate = True
        elif not same_gate and changed and isinstance(prior_deps, Mapping):
            invalidate = any(
                key in changed and prior_deps.get(key) != identities.get(key)
                for key in changed
            )
        if invalidate:
            prior_receipt = row.get("receipt_path")
            candidate = {
                "gate": prior_gate,
                "reason": "dependency identity changed" if prior_gate != gate else "gate rerun changed evidence",
                "prior_receipt": prior_receipt,
            }
            if isinstance(row.get("receipt_sha256"), str):
                candidate["prior_receipt_sha256"] = row["receipt_sha256"]
            if candidate not in invalidated:
                invalidated.append(candidate)
        elif not same_gate:
            completed.append(_deepcopy(dict(row)))
    completed.append(
        {
            "gate": gate,
            "receipt_path": _repo_relative(receipt_path),
            "receipt_sha256": receipt_sha256,
            "artifact_paths": sorted({_repo_relative(Path(path)) for path in artifact_paths}, key=lambda item: item.encode("utf-8", "strict")),
            "dependency_hashes": _deepcopy(dict(dependency_hashes)),
        }
    )
    completed.sort(key=lambda row: (_gate_rank(str(row["gate"])), str(row["gate"]).encode("utf-8", "strict")))
    invalidated.sort(key=lambda row: (_gate_rank(str(row.get("gate", ""))), str(row.get("gate", "")).encode("utf-8", "strict"), str(row.get("prior_receipt", ""))))
    merged_sources: dict[str, dict[str, Any]] = {}
    if old:
        for row in old.get("source_hashes", []):
            if isinstance(row, Mapping) and isinstance(row.get("path"), str):
                merged_sources[str(row["path"])] = dict(row)
    for row in source_rows:
        merged_sources[str(row["path"])] = _deepcopy(dict(row))
    source_values = sorted(merged_sources.values(), key=lambda row: row["path"].encode("utf-8", "strict"))
    artifacts: set[str] = set(old.get("artifact_paths", [])) if old else set()
    for row in completed:
        for path in row.get("artifact_paths", []):
            if isinstance(path, str):
                artifacts.add(path)
    artifacts.update(_repo_relative(Path(path)) for path in artifact_paths)
    body: dict[str, Any] = {
        "schema": _WORKFLOW_STATUS_SCHEMA,
        "version": 1,
        "source_hashes": source_values,
        "current": _deepcopy(dict(identities)),
        "completed_gates": completed,
        "artifact_paths": sorted(artifacts, key=lambda item: item.encode("utf-8", "strict")),
        "invalidated_descendants": invalidated,
    }
    body["self_sha256"] = canonical_hash(body, _WORKFLOW_STATUS_DOMAIN)
    return body


def _write_status(status: Mapping[str, Any]) -> None:
    _atomic_file(_DIAG / "cassi-fi-status.json", _canonical(status, context="workflow status"))


def _receipt(body: Mapping[str, Any], domain: str) -> dict[str, Any]:
    result = _deepcopy(dict(body))
    result.pop("self_sha256", None)
    result["self_sha256"] = canonical_hash(result, domain)
    _canonical(result, context="workflow receipt")
    return result


def _capture_summary(output: str) -> dict[str, Any]:
    raw = output.encode("utf-8", "strict")
    return {"byte_count": len(raw), "line_count": len(output.splitlines()), "sha256": _sha256_bytes(raw)}


@contextlib.contextmanager
def _capture() -> Any:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        yield stdout, stderr


def _load_registry_entries() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest_path = _DIAG / "cassi-fi-schema-registry" / "manifest.json"
    if not manifest_path.exists():
        _fail("REGISTRY_UNAVAILABLE", "normalized schema registry manifest is unavailable")
    manifest_raw, manifest = _load_json(manifest_path)
    if not isinstance(manifest, Mapping) or manifest.get("schema") != SCHEMA_REGISTRY_SCHEMA:
        _fail("REGISTRY_INVALID", "normalized schema registry manifest has the wrong schema")
    if manifest_raw != _canonical(manifest, context="schema registry manifest"):
        _fail("REGISTRY_INVALID", "normalized schema registry manifest is not canonical JSON")
    if (
        not isinstance(manifest, Mapping)
        or set(manifest) != {
            "schema",
            "version",
            "entry_keys",
            "source_hashes",
            "shards",
            "entry_hashes",
            "entry_count",
            "first_schema",
            "last_schema",
            "self_sha256",
        }
        or manifest.get("schema") != SCHEMA_REGISTRY_SCHEMA
        or manifest.get("version") != 1
    ):
        _fail("REGISTRY_INVALID", "normalized schema registry manifest fields mismatch")
    body = dict(manifest)
    supplied = body.pop("self_sha256")
    if supplied != canonical_hash(body, SCHEMA_REGISTRY_SCHEMA):
        _fail("REGISTRY_INVALID", "normalized schema registry manifest self hash mismatch")
    if manifest.get("entry_keys") != list(_ENTRY_KEYS):
        _fail("REGISTRY_INVALID", "registry manifest normalized entry key set mismatch")
    shard_rows = manifest.get("shards")
    if not isinstance(shard_rows, list) or not shard_rows:
        _fail("REGISTRY_INVALID", "registry manifest has no shards")
    entries: list[dict[str, Any]] = []
    shard_row_keys = {
        "path",
        "raw_sha256",
        "byte_count",
        "entry_count",
        "first_schema",
        "last_schema",
    }
    for row in shard_rows:
        if not isinstance(row, Mapping) or set(row) != shard_row_keys:
            _fail("REGISTRY_INVALID", "registry shard row is invalid")
        relative = row.get("path")
        if not isinstance(relative, str) or not relative.startswith("shards/"):
            _fail("REGISTRY_INVALID", "registry shard path is invalid")
        shard_path = manifest_path.parent / relative
        if not shard_path.exists():
            _fail("REGISTRY_INVALID", f"registry shard is missing: {relative}")
        raw, shard = _load_json(shard_path)
        if (
            _sha256_bytes(raw) != row.get("raw_sha256")
            or len(raw) != row.get("byte_count")
            or len(raw) > MAX_CANONICAL_BYTES
        ):
            _fail("REGISTRY_INVALID", f"registry shard hash or byte count mismatch: {relative}")
        if raw != _canonical(shard, context=f"registry shard {relative}"):
            _fail("REGISTRY_INVALID", f"registry shard is not canonical JSON: {relative}")
        if not isinstance(shard, Mapping) or set(shard) != {
            "schema",
            "entries",
            "entry_count",
            "first_schema",
            "last_schema",
            "self_sha256",
        }:
            _fail("REGISTRY_INVALID", f"registry shard fields mismatch: {relative}")
        if shard.get("schema") != _REGISTRY_SHARD_SCHEMA:
            _fail("REGISTRY_INVALID", f"registry shard schema mismatch: {relative}")
        shard_body = dict(shard)
        shard_self = shard_body.pop("self_sha256")
        if shard_self != canonical_hash(shard_body, _REGISTRY_SHARD_SCHEMA):
            _fail("REGISTRY_INVALID", f"registry shard self hash mismatch: {relative}")
        shard_entries = shard.get("entries")
        if not isinstance(shard_entries, list) or not shard_entries:
            _fail("REGISTRY_INVALID", f"registry shard entries are invalid: {relative}")
        if (
            shard.get("entry_count") != len(shard_entries)
            or row.get("entry_count") != len(shard_entries)
            or shard.get("first_schema") != shard_entries[0].get("schema")
            or shard.get("last_schema") != shard_entries[-1].get("schema")
            or row.get("first_schema") != shard.get("first_schema")
            or row.get("last_schema") != shard.get("last_schema")
        ):
            _fail("REGISTRY_INVALID", f"registry shard bounds mismatch: {relative}")
        for index, entry in enumerate(shard_entries):
            if not isinstance(entry, Mapping):
                _fail("REGISTRY_INVALID", f"registry shard entry is invalid: {relative}/{index}")
            entries.append(dict(entry))
    schemas = [entry.get("schema") for entry in entries]
    if (
        any(not isinstance(schema, str) for schema in schemas)
        or schemas != sorted(schemas, key=lambda schema: schema.encode("utf-8", "strict"))
        or len(schemas) != len(set(schemas))
    ):
        _fail("REGISTRY_INVALID", "registry entries are not globally byte-sorted and unique")
    expected_hashes = manifest.get("entry_hashes")
    if not isinstance(expected_hashes, list) or len(expected_hashes) != len(entries):
        _fail("REGISTRY_INVALID", "registry manifest entry hash count mismatch")
    for entry, expected in zip(entries, expected_hashes, strict=True):
        if not isinstance(expected, Mapping) or set(expected) != {"schema", "sha256"} or expected.get("schema") != entry.get("schema"):
            _fail("REGISTRY_INVALID", "registry manifest entry hash schema mismatch")
        if canonical_hash(entry, SCHEMA_REGISTRY_ENTRY_HASH_DOMAIN) != expected.get("sha256"):
            _fail("REGISTRY_INVALID", f"registry entry hash mismatch: {entry.get('schema')}")
    if (
        manifest.get("entry_count") != len(entries)
        or manifest.get("first_schema") != schemas[0]
        or manifest.get("last_schema") != schemas[-1]
    ):
        _fail("REGISTRY_INVALID", "registry manifest entry bounds mismatch")
    return entries, dict(manifest)


def _schema_replay_evidence() -> dict[str, Any]:
    entries, manifest = _load_registry_entries()
    replay_count = 0
    fixture_count = 0
    for index, entry in enumerate(entries):
        if set(entry) != _ENTRY_KEY_SET:
            _fail("ENTRY_FIELDS_INVALID", f"materialized entry[{index}] does not have the exact normalized key set")
        normalized = _normalise_entry(entry, context=f"materialized/{entry.get('schema', index)}")
        if normalized != entry:
            _fail(
                "ENTRY_NORMALIZATION_MISMATCH",
                f"materialized entry {entry.get('schema', index)} is not the deterministic normalized form",
            )
        fixture_count += 2 + len(entry["canonical_fixture_set"]["nullable_valid"])
        replay_count += len(entry["mutation_controls"])
    return {
        "status": "PASS",
        "registry_manifest_path": _repo_relative(_DIAG / "cassi-fi-schema-registry" / "manifest.json"),
        "registry_sha256": manifest["self_sha256"],
        "entry_count": len(entries),
        "fixture_count": fixture_count,
        "mutation_replay_count": replay_count,
    }


def _profile_command() -> dict[str, Any]:
    profile_id = "qi-flow-development-v1"
    if _DEVELOPMENT_PROFILE.exists():
        _, old_payload = _load_json(_DEVELOPMENT_PROFILE)
        if (
            not isinstance(old_payload, Mapping)
            or not isinstance(old_payload.get("profile"), Mapping)
            or not isinstance(old_payload["profile"].get("profile_id"), str)
            or not old_payload["profile"]["profile_id"]
        ):
            _fail("PROFILE_INVALID", "development profile input has no valid profile_id")
        profile_id = old_payload["profile"]["profile_id"]
    try:
        profile = QiFlowProfile.from_defaults(profile_id=profile_id)
        root = validate_contract_root(build_contract_root(profile))
        profile = validate_profile(profile)
    except Exception as exc:
        _fail("PROFILE_INVALID", f"cannot materialize profile: {exc}")
    config = {
        "schema": "cassi.qi-flow-development-config.v1",
        "w0_run_id": W0_RUN_ID,
        "historical_manifest_sha256": W0_HISTORICAL_MANIFEST_SHA256,
        "profile": {"profile_id": profile_id, **_deepcopy(dict(PROFILE_DEFAULTS))},
    }
    config_bytes = _canonical(config, context="development profile")
    source_paths = [
        _REPOSITORY / "cassi_qi_bootstrap.py",
        _REPOSITORY / "cassi_qi_profile.py",
    ]
    sources = _source_rows(source_paths)
    identities = _identity_context(profile, root)
    receipt_body = {
        "schema": _PROFILE_RECEIPT_SCHEMA,
        "status": "PASS",
        "profile_path": _repo_relative(_DEVELOPMENT_PROFILE),
        "profile_mirror_path": _repo_relative(_PROFILE_OUTPUT),
        "profile_sha256": profile.profile_sha256,
        "contract_root_sha256": root.sha256,
        "projection_registry_sha256": root.payload["projection_registry"]["sha256"],
        "source_hashes": sources,
        "artifact_paths": [_repo_relative(_DEVELOPMENT_PROFILE), _repo_relative(_PROFILE_OUTPUT)],
    }
    receipt = _receipt(receipt_body, _PROFILE_RECEIPT_DOMAIN)
    receipt_path = _DIAG / "cassi-fi-profile-receipt.json"
    status = _status_update(
        gate="profile",
        receipt_path=receipt_path,
        receipt_sha256=receipt["self_sha256"],
        artifact_paths=[_DEVELOPMENT_PROFILE, _PROFILE_OUTPUT, receipt_path],
        dependency_hashes=identities,
        source_rows=sources,
        identities=identities,
    )
    _DIAG.mkdir(parents=True, exist_ok=True)
    _atomic_file(_DEVELOPMENT_PROFILE, config_bytes)
    _atomic_file(_PROFILE_OUTPUT, config_bytes)
    _atomic_file(receipt_path, _canonical(receipt, context="profile receipt"))
    _write_status(status)
    return receipt


def _publish_registry(stage: Path, manifest: Mapping[str, Any], source_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    destination = _DIAG / "cassi-fi-schema-registry"
    receipt_path = _DIAG / "cassi-fi-schema-receipt.json"
    identities = _identity_context(registry_sha256=str(manifest["self_sha256"]))
    relative_shards = [Path(str(row["path"])) for row in manifest["shards"]]
    diag_paths = [destination / path for path in relative_shards]
    source_paths = [_SOURCE_REGISTRY / path for path in relative_shards]
    artifact_paths = [
        destination / "manifest.json",
        *diag_paths,
        _SOURCE_REGISTRY / "manifest.json",
        *source_paths,
    ]
    receipt_body = {
        "schema": "cassi.qi-flow-fi-schema-receipt.v1",
        "status": "PASS",
        "manifest_path": _repo_relative(destination / "manifest.json"),
        "source_manifest_path": _repo_relative(_SOURCE_REGISTRY / "manifest.json"),
        "manifest_sha256": manifest["self_sha256"],
        "entry_count": manifest["entry_count"],
        "shard_count": len(manifest["shards"]),
        "first_schema": manifest["first_schema"],
        "last_schema": manifest["last_schema"],
        "source_hashes": [_deepcopy(dict(row)) for row in source_rows],
        "artifact_paths": [_repo_relative(path) for path in artifact_paths],
    }
    receipt = _receipt(receipt_body, "cassi.qi-flow-fi-schema-receipt.v1")
    status = _status_update(
        gate="schemas",
        receipt_path=receipt_path,
        receipt_sha256=receipt["self_sha256"],
        artifact_paths=[*artifact_paths, receipt_path],
        dependency_hashes=identities,
        source_rows=source_rows,
        identities=identities,
    )
    source_stage = Path(tempfile.mkdtemp(prefix=".cassi-fi-schema-source-", dir=_REPOSITORY))
    try:
        shutil.copytree(stage, source_stage, dirs_exist_ok=True)
        _atomic_directory(source_stage, _SOURCE_REGISTRY)
        _atomic_directory(stage, destination)
    finally:
        if source_stage.exists():
            shutil.rmtree(source_stage, ignore_errors=True)
    _atomic_file(receipt_path, _canonical(receipt, context="schema receipt"))
    _write_status(status)
    return receipt


def _schemas_command(positional: Sequence[str], options: Sequence[str] | None) -> dict[str, Any]:
    paths = _discover_schema_paths(positional, options)
    entries, source_rows = _normalise_registry(paths)
    _DIAG.mkdir(parents=True, exist_ok=True)
    stage, manifest = _stage_registry(entries, source_rows)
    try:
        return _publish_registry(stage, manifest, source_rows)
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def _delivery_command(name: str, source: str) -> dict[str, Any]:
    if re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name) is None:
        _fail("DELIVERY_NAME_INVALID", "delivery name must match [a-z0-9][a-z0-9_-]*")
    source_path = Path(source).resolve()
    raw, payload = _load_json(source_path)
    rows = _expand_input(payload, context=str(source_path))
    schemas: list[str] = []
    for index, row in enumerate(rows):
        entry = _normalise_entry(row, context=f"delivery/{name}/{index}")
        if entry["schema"] in schemas:
            _fail("DUPLICATE_SCHEMA", f"delivery {name} repeats {entry['schema']}")
        schemas.append(entry["schema"])
    schemas.sort(key=lambda value: value.encode("utf-8", "strict"))
    installed = _canonical_unbounded(payload, context=f"delivery/{name}") + b"\n"
    target = _DIAG / "cassi-fi-schema-inputs" / f"{name}.json"
    receipt_path = _DIAG / "cassi-fi-deliveries" / f"{name}.json"
    receipt = _receipt(
        {
            "schema": _DELIVERY_RECEIPT_SCHEMA,
            "status": "PASS",
            "delivery": name,
            "source_path": source_path.as_posix(),
            "source_sha256": _sha256_bytes(raw),
            "installed_path": _repo_relative(target),
            "installed_sha256": _sha256_bytes(installed),
            "byte_count": len(installed),
            "entry_count": len(schemas),
            "schemas": schemas,
            "artifact_paths": [_repo_relative(target), _repo_relative(receipt_path)],
        },
        _DELIVERY_RECEIPT_DOMAIN,
    )
    _atomic_file(target, installed)
    _atomic_file(receipt_path, _canonical(receipt, context=f"delivery/{name}/receipt"))
    return receipt


def _state_roundtrip(profile: QiFlowProfile) -> dict[str, Any]:
    try:
        from cassi_qi_field import QiFlowStateV3, dump_v3_state_bytes, load_v3_state_bytes, v3_state_identity
        state = QiFlowStateV3.create(profile, batch_lanes=1)
        dumped = dump_v3_state_bytes(state, profile)
        restored = load_v3_state_bytes(dumped, profile)
        restored_dump = dump_v3_state_bytes(restored, profile)
        identity = v3_state_identity(state, profile)
    except Exception as exc:
        _fail("STATE_ROUNDTRIP_FAILED", f"state create/dump/load failed: {exc}")
    if dumped != restored_dump:
        _fail("STATE_BYTE_IDENTITY_FAILED", "state dump/load bytes are not identical")
    return {
        "status": "PASS",
        "raw_byte_count": len(dumped),
        "raw_sha256": _sha256_bytes(dumped),
        "state_sha256": identity.get("state_sha256"),
        "profile_sha256": profile.profile_sha256,
        "bytes_identical": True,
        "payload": dumped,
    }


def _tail_control(profile: QiFlowProfile) -> dict[str, Any]:
    try:
        from cassi_qi_field import QiFlowStateV3, dump_v3_state_bytes
        shapes = [list(shape) for shape in profile.payload["field"]["active_shapes"]]
        if len(shapes) < 1:
            _fail("TAIL_CONTROL_FAILED", "profile declares no active sheets")
        shapes[-1] = [3, 8]
        if int(profile.payload["field"]["mode_count"]) < 24:
            _fail("TAIL_CONTROL_FAILED", "profile cannot represent the [3,8] active rectangle")
        overrides = derive_rectangular_profile_overrides(profile, shapes)
        derived = QiFlowProfile.from_defaults(profile_id=f"{profile.payload['profile_id']}-tail-control", overrides=overrides)
        state = QiFlowStateV3.create(derived, batch_lanes=1)
        component_count = int(derived.payload["field"]["component_count"])
        mode_count = int(derived.payload["field"]["mode_count"])
        active_count = 3 * 8
        view = state.field[-1].reshape(component_count, mode_count, 1)
        zero_tail = bool(view[:, active_count:, :].eq(0).all().item())
        if not zero_tail:
            _fail("TAIL_ZERO_CONTROL_FAILED", "derived [3,8] inactive tail is not zero")
        tampered = state.field.clone()
        tampered_view = tampered[-1].reshape(component_count, mode_count, 1)
        tampered_view[:, active_count:, :] = 1.0
        try:
            dump_v3_state_bytes(QiFlowStateV3(tampered), derived)
        except Exception:
            nonzero_rejected = True
        else:
            nonzero_rejected = False
        if not nonzero_rejected:
            _fail("TAIL_NONZERO_ACCEPTED", "derived [3,8] nonzero tail was accepted")
    except WorkflowError:
        raise
    except Exception as exc:
        _fail("TAIL_CONTROL_FAILED", f"derived [3,8] control failed: {exc}")
    return {
        "status": "PASS",
        "derived_active_shapes": shapes,
        "tail_scale": len(shapes) - 1,
        "tail_active_sites": active_count,
        "zero_tail": zero_tail,
        "nonzero_tail_rejected": nonzero_rejected,
        "profile_sha256": derived.profile_sha256,
    }


def _collect_files(root: Path) -> list[str]:
    if root.is_file():
        return [_repo_relative(root)]
    if not root.exists() or not root.is_dir():
        return []
    paths = [path for path in root.rglob("*") if path.is_file()]
    paths.sort(key=lambda path: _repo_relative(path).encode("utf-8", "strict"))
    return [_repo_relative(path) for path in paths]


def _g1_command() -> dict[str, Any]:
    components: list[dict[str, Any]] = []
    artifact_paths: list[Path] = []
    try:
        profile, root = _profile_identity()
        components.append({"name": "profile_root_validation", "status": "PASS", "profile_sha256": profile.profile_sha256, "contract_root_sha256": root.sha256})
    except WorkflowError as exc:
        components.append({"name": "profile_root_validation", "status": "FAIL", "error_code": exc.code})
        return _g1_failure(components, artifact_paths, exc)
    try:
        state_result = _state_roundtrip(profile)
        state_path = _DIAG / "cassi-fi-g1-state" / f"{state_result['raw_sha256']}.qiflow"
        artifact_paths.append(state_path)
        components.append({key: value for key, value in state_result.items() if key != "payload"})
    except WorkflowError as exc:
        components.append({"name": "state_roundtrip", "status": "FAIL", "error_code": exc.code})
        return _g1_failure(components, artifact_paths, exc)
    try:
        _DIAG.mkdir(parents=True, exist_ok=True)
        _atomic_file(state_path, state_result["payload"])
    except WorkflowError as exc:
        components.append({"name": "state_artifact", "status": "FAIL", "error_code": exc.code})
        return _g1_failure(components, artifact_paths, exc)
    components[-1]["name"] = "state_roundtrip"
    try:
        tail_result = _tail_control(profile)
        tail_result["name"] = "tail_zero_and_nonzero_control"
        components.append(tail_result)
    except WorkflowError as exc:
        components.append({"name": "tail_zero_and_nonzero_control", "status": "FAIL", "error_code": exc.code})
        return _g1_failure(components, artifact_paths, exc)
    try:
        components.append({"name": "schema_fixture_and_mutation_replay", **_schema_replay_evidence()})
    except WorkflowError as exc:
        components.append({"name": "schema_fixture_and_mutation_replay", "status": "FAIL", "error_code": exc.code})
        return _g1_failure(components, artifact_paths, exc)
    candidate_value, call, call_error = _captured_call(
        "run_cassi_qi_w1.run",
        lambda: _call_entry_point(
            "run_cassi_qi_w1",
            "run",
            (_materialized_profile_path(),),
        ),
    )
    candidate_component = {
        "name": "w1_candidate_production",
        "status": "FAIL" if call_error is not None else "PASS",
        **call,
    }
    components.append(candidate_component)
    if call_error is not None:
        error = WorkflowError("W1_CANDIDATE_FAILED", str(call_error))
        candidate_component["error_code"] = error.code
        return _g1_failure(components, artifact_paths, error)
    if not isinstance(candidate_value, (str, os.PathLike)):
        error = WorkflowError("W1_CANDIDATE_MISSING", "W1 runner returned no artifact path")
        candidate_component["status"] = "FAIL"
        candidate_component["error_code"] = error.code
        return _g1_failure(components, artifact_paths, error)
    candidate = Path(candidate_value).resolve()
    if not candidate.exists() or not candidate.is_dir():
        error = WorkflowError("W1_CANDIDATE_MISSING", "W1 runner returned an unavailable artifact path")
        candidate_component["status"] = "FAIL"
        candidate_component["error_code"] = error.code
        return _g1_failure(components, artifact_paths, error)
    candidate_component["artifact_path"] = _repo_relative(candidate)
    artifact_paths.extend(_REPOSITORY / item for item in _collect_files(candidate))
    verification_value, call, call_error = _captured_call(
        "verify_cassi_qi_flow.verify_g1_identity",
        lambda: _call_entry_point(
            "verify_cassi_qi_flow",
            "verify_g1_identity",
            (candidate,),
            {"bootstrap_identity": bootstrap_identity()},
        ),
    )
    verification_component = {
        "name": "independent_g1_verification",
        "status": "FAIL" if call_error is not None else "PASS",
        **call,
    }
    components.append(verification_component)
    if call_error is not None:
        error = WorkflowError("G1_VERIFIER_FAILED", str(call_error))
        verification_component["error_code"] = error.code
        return _g1_failure(components, artifact_paths, error)
    if not isinstance(verification_value, Mapping) or verification_value.get("status") != "PASS":
        error = WorkflowError("G1_VERIFIER_FAILED", "independent G1 verifier did not return PASS")
        verification_component["status"] = "FAIL"
        verification_component["error_code"] = error.code
        return _g1_failure(components, artifact_paths, error)
    verification = dict(verification_value)
    verification_component["result_sha256"] = canonical_hash(verification, _G1_RECEIPT_DOMAIN)
    receipt_path = _DIAG / "cassi-fi-g1-receipt.json"
    registry_sha = _manifest_identity()
    identities = _identity_context(profile, root, registry_sha256=registry_sha)
    receipt = _receipt(
        {
            "schema": _G1_RECEIPT_SCHEMA,
            "status": "PASS",
            "gate": "G1",
            "components": components,
            "candidate_path": _repo_relative(candidate),
            "artifact_paths": sorted(set(_repo_relative(path) for path in artifact_paths), key=lambda item: item.encode("utf-8", "strict")),
            "gate_result": "PASS",
            "dependency_hashes": identities,
        },
        _G1_RECEIPT_DOMAIN,
    )
    status = _status_update(
        gate="G1",
        receipt_path=receipt_path,
        receipt_sha256=receipt["self_sha256"],
        artifact_paths=[candidate, *artifact_paths, receipt_path],
        dependency_hashes=identities,
        source_rows=_source_rows([_REPOSITORY / "cassi_qi_bootstrap.py", _REPOSITORY / "cassi_qi_profile.py", _REPOSITORY / "cassi_qi_field.py", _REPOSITORY / "run_cassi_qi_w1.py", _REPOSITORY / "verify_cassi_qi_flow.py"]),
        identities=identities,
    )
    _atomic_file(receipt_path, _canonical(receipt, context="G1 receipt"))
    _write_status(status)
    return receipt


def _g1_failure(components: Sequence[Mapping[str, Any]], artifact_paths: Sequence[Path], error: WorkflowError) -> dict[str, Any]:
    receipt_path = _DIAG / "cassi-fi-g1-receipt.json"
    _DIAG.mkdir(parents=True, exist_ok=True)
    receipt = _receipt(
        {
            "schema": _G1_RECEIPT_SCHEMA,
            "status": "FAIL",
            "gate": "G1",
            "components": [_deepcopy(dict(row)) for row in components],
            "candidate_path": next((path for path in (_repo_relative(item) for item in artifact_paths) if "w1-final" in path), None),
            "artifact_paths": sorted(set(_repo_relative(path) for path in artifact_paths), key=lambda item: item.encode("utf-8", "strict")),
            "gate_result": "FAIL",
            "failure": {"code": error.code, "message": error.message},
        },
        _G1_RECEIPT_DOMAIN,
    )
    _atomic_file(receipt_path, _canonical(receipt, context="G1 failure receipt"))
    return receipt


def _call_entry_point(
    module_name: str,
    function_name: str,
    args: Sequence[Any] = (),
    kwargs: Mapping[str, Any] | None = None,
) -> Any:
    import importlib

    module = importlib.import_module(module_name)
    function = getattr(module, function_name, None)
    if not callable(function):
        _fail("WP_UNAVAILABLE", f"{module_name}.{function_name} is unavailable")
    return function(*args, **dict(kwargs or {}))


def _captured_call(entry_point: str, action: Callable[[], Any]) -> tuple[Any | None, dict[str, Any], Exception | None]:
    with _capture() as (stdout, stderr):
        try:
            result = action()
        except Exception as exc:
            error: Exception | None = exc
            result = None
        else:
            error = None
    evidence: dict[str, Any] = {
        "entry_point": entry_point,
        "return_code": 1 if error is not None else 0,
        "stdout": _capture_summary(stdout.getvalue()),
        "stderr": _capture_summary(stderr.getvalue()),
    }
    if error is not None:
        evidence["error"] = {
            "type": type(error).__name__,
            "message": str(error).replace("\n", " ").strip(),
        }
    return result, evidence, error


_WORK_PACKAGE_DISPATCH: dict[str, dict[str, Any]] = {
    "W1": {
        "run": ("run_cassi_qi_w1", "run"),
        "verify": ("verify_cassi_qi_flow", "verify_g1_identity"),
        "pass_statuses": ("PASS",),
    },
    "W2": {
        "run": ("run_cassi_qi_geometry", "run"),
        "verify": ("verify_cassi_qi_geometry", "verify_artifact"),
        "pass_statuses": ("PASS_W2_G2",),
    },
    "W3": {
        "run": ("run_cassi_qi_flow", "run_artifact"),
        "verify": ("verify_cassi_qi_transport", "verify_artifact"),
        "pass_statuses": ("PASS_W3_G3",),
    },
    "W3N": {
        "run": ("run_cassi_qi_numerical_certificate", "run_artifact"),
        "verify": ("verify_cassi_qi_numerical_certificate", "verify"),
        "pass_statuses": ("PASS", "PASS_W3N_G3N"),
    },
    "W4": {
        "run": ("run_cassi_qi_carrier", "run_artifact"),
        "verify": ("verify_cassi_qi_carrier", "verify"),
        "pass_statuses": ("PASS_W4_G4",),
    },
    "W4R": {
        "run": ("run_cassi_qi_topology", "run_artifact"),
        "verify": ("verify_cassi_qi_topology", "verify"),
        "pass_statuses": ("PASS_W4R_G4R",),
    },
    "W5": {
        "run": ("run_cassi_qi_conversion", "run_artifact"),
        "verify": ("verify_cassi_qi_conversion", "verify"),
        "pass_statuses": ("PASS_W5_G5",),
    },
    "W5V": {
        "run": ("run_cassi_qi_conversion_viability", "run_artifact"),
        "verify": ("verify_cassi_qi_conversion_viability", "verify"),
        "pass_statuses": ("PASS_W5V_G5V",),
    },
    "W6": {
        "run": ("run_cassi_qi_exchange", "run"),
        "verify": ("verify_cassi_qi_exchange", "verify"),
        "pass_statuses": ("PASS",),
    },
}


def _normalise_work_package(token: str) -> str:
    supported = ", ".join(_WORK_PACKAGE_DISPATCH)
    if not isinstance(token, str) or not token.strip():
        _fail("UNKNOWN_WORK_PACKAGE", f"supported values are {supported}")
    compact = re.sub(r"[^A-Za-z0-9]", "", token).upper()
    aliases = {
        "1": "W1",
        "W1": "W1",
        "WP1": "W1",
        "W01": "W1",
        "WP01": "W1",
        "W1G1": "W1",
        "WP1G1": "W1",
        "2": "W2",
        "W2": "W2",
        "WP2": "W2",
        "W02": "W2",
        "WP02": "W2",
        "W2G2": "W2",
        "WP2G2": "W2",
        "3": "W3",
        "W3": "W3",
        "WP3": "W3",
        "W03": "W3",
        "WP03": "W3",
        "W3G3": "W3",
        "WP3G3": "W3",
        "3N": "W3N",
        "W3N": "W3N",
        "WP3N": "W3N",
        "W03N": "W3N",
        "WP03N": "W3N",
        "W3NG3N": "W3N",
        "WP3NG3N": "W3N",
        "4": "W4",
        "W4": "W4",
        "WP4": "W4",
        "W4R": "W4R",
        "WP4R": "W4R",
        "5": "W5",
        "W5": "W5",
        "WP5": "W5",
        "W5V": "W5V",
        "WP5V": "W5V",
        "6": "W6",
        "W6": "W6",
        "WP6": "W6",
    }
    package = aliases.get(compact)
    if package in _WORK_PACKAGE_DISPATCH:
        return package
    _fail("UNKNOWN_WORK_PACKAGE", f"unsupported work package {token!r}; supported values are {supported}")
    raise AssertionError("unreachable")


def _verify_work_package(token: str) -> dict[str, Any]:
    package = _normalise_work_package(token)
    spec = _WORK_PACKAGE_DISPATCH[package]
    receipt_path = _DIAG / f"cassi-fi-verify-{package.lower()}-receipt.json"
    calls: list[dict[str, Any]] = []
    artifacts: list[Path] = []
    result: Mapping[str, Any] | None = None
    error: WorkflowError | None = None
    run_module, run_function = spec["run"]
    run_label = f"{run_module}.{run_function}"
    run_args: tuple[Any, ...] = (_materialized_profile_path(),) if package == "W1" else ()
    artifact_value, call, call_error = _captured_call(
        run_label,
        lambda: _call_entry_point(run_module, run_function, run_args),
    )
    calls.append(call)
    if call_error is not None:
        error = WorkflowError("WP_RUN_FAILED", f"{run_label}: {call_error}")
    else:
        if not isinstance(artifact_value, (str, os.PathLike)):
            error = WorkflowError("WP_ARTIFACT_MISSING", f"{run_label} returned no artifact path")
        else:
            artifact = Path(artifact_value).resolve()
            if not artifact.exists():
                error = WorkflowError("WP_ARTIFACT_MISSING", f"{run_label} returned an unavailable artifact")
            else:
                artifacts.append(artifact)
    if error is None:
        verify_module, verify_function = spec["verify"]
        verify_label = f"{verify_module}.{verify_function}"
        verify_kwargs = {"bootstrap_identity": bootstrap_identity()} if package == "W1" else {}
        result_value, call, call_error = _captured_call(
            verify_label,
            lambda: _call_entry_point(
                verify_module,
                verify_function,
                (artifacts[0],),
                verify_kwargs,
            ),
        )
        calls.append(call)
        if call_error is not None:
            error = WorkflowError("WP_VERIFICATION_FAILED", f"{verify_label}: {call_error}")
        elif not isinstance(result_value, Mapping):
            error = WorkflowError("WP_VERIFICATION_FAILED", f"{verify_label} returned no evidence mapping")
        else:
            result = dict(result_value)
            if result.get("status") not in spec["pass_statuses"]:
                error = WorkflowError("WP_VERIFICATION_FAILED", f"{verify_label} did not return PASS")
    artifact_paths: list[Path] = []
    for artifact in artifacts:
        artifact_paths.extend(_REPOSITORY / item for item in _collect_files(artifact))
    identities = _identity_context()
    body: dict[str, Any] = {
        "schema": _WP_RECEIPT_SCHEMA,
        "status": "FAIL" if error is not None else "PASS",
        "work_package": package,
        "artifact_roots": [_repo_relative(path) for path in artifacts],
        "calls": calls,
        "artifact_paths": sorted(
            {_repo_relative(path) for path in artifact_paths},
            key=lambda item: item.encode("utf-8", "strict"),
        ),
        "result_sha256": canonical_hash(dict(result), _WP_RECEIPT_DOMAIN) if result is not None else None,
        "dependency_hashes": identities,
    }
    if error is not None:
        body["failure"] = {"code": error.code, "message": error.message}
    receipt = _receipt(body, _WP_RECEIPT_DOMAIN)
    _DIAG.mkdir(parents=True, exist_ok=True)
    status = None
    if error is None:
        source_paths = [
            _REPOSITORY / "cassi_qi_bootstrap.py",
            _REPOSITORY / "cassi_qi_profile.py",
            _REPOSITORY / f"{run_module}.py",
            _REPOSITORY / f"{spec['verify'][0]}.py",
        ]
        status = _status_update(
            gate=package,
            receipt_path=receipt_path,
            receipt_sha256=receipt["self_sha256"],
            artifact_paths=[*artifacts, *artifact_paths, receipt_path],
            dependency_hashes=identities,
            source_rows=_source_rows(source_paths),
            identities=identities,
        )
    _atomic_file(receipt_path, _canonical(receipt, context="work-package receipt"))
    if status is not None:
        _write_status(status)
    return receipt


def _batch_command(tokens: Sequence[str]) -> dict[str, Any]:
    requested = {_normalise_work_package(token) for token in tokens}
    packages = [name for name in _WORK_PACKAGE_DISPATCH if name in requested]
    components: list[dict[str, Any]] = []
    failed: list[str] = []
    artifact_paths: list[str] = []
    for package in packages:
        receipt = _verify_work_package(package)
        receipt_path = _DIAG / f"cassi-fi-verify-{package.lower()}-receipt.json"
        artifact_paths.append(_repo_relative(receipt_path))
        components.append(
            {
                "work_package": package,
                "status": receipt["status"],
                "receipt_path": _repo_relative(receipt_path),
                "receipt_sha256": receipt["self_sha256"],
            }
        )
        if receipt["status"] != "PASS":
            failed.append(package)
    body: dict[str, Any] = {
        "schema": _BATCH_RECEIPT_SCHEMA,
        "status": "FAIL" if failed else "PASS",
        "work_packages": packages,
        "pass_count": len(packages) - len(failed),
        "fail_count": len(failed),
        "components": components,
        "artifact_paths": artifact_paths,
    }
    if failed:
        body["failure"] = {
            "code": "BATCH_VERIFICATION_FAILED",
            "message": f"failed work packages: {', '.join(failed)}",
        }
    receipt = _receipt(body, _BATCH_RECEIPT_DOMAIN)
    receipt_path = _DIAG / "cassi-fi-batch-receipt.json"
    _atomic_file(receipt_path, _canonical(receipt, context="batch receipt"))
    return receipt


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise WorkflowError("ARGUMENT_ERROR", message)


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(prog="run_cassi_fi_workflow.py", description="Deterministic CassiFI contract and evidence workflow")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    schemas = commands.add_parser("schemas", help="normalize and atomically shard the complete schema registry")
    schemas.add_argument("inputs", nargs="*", metavar="INPUT")
    schemas.add_argument("--input", action="append", dest="option_inputs", default=[], metavar="INPUT")
    deliver = commands.add_parser("deliver", help="validate and atomically install one schema artifact bundle")
    deliver.add_argument("name", metavar="NAME")
    deliver.add_argument("source", metavar="SOURCE")
    commands.add_parser("profile", help="regenerate and validate both development-profile copies")
    commands.add_parser("g1", help="run the complete W1/G1 evidence batch")
    verify = commands.add_parser("verify", help="run one focused work package")
    verify.add_argument("wp", metavar="WP")
    batch = commands.add_parser("batch", help="run selected focused work packages and emit one compact receipt")
    batch.add_argument("wps", nargs="+", metavar="WP")
    return parser


def _print_success(receipt: Mapping[str, Any]) -> None:
    sys.stdout.buffer.write(_canonical(receipt, context="success receipt") + b"\n")


def _print_error(error: WorkflowError) -> None:
    payload = {
        "schema": "cassi.qi-flow-workflow-error.v1",
        "status": "FAIL",
        "code": error.code,
        "message": error.message,
    }
    sys.stderr.buffer.write(_canonical(payload, context="workflow error") + b"\n")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.command == "schemas":
            receipt = _schemas_command(args.inputs, args.option_inputs)
        elif args.command == "deliver":
            receipt = _delivery_command(args.name, args.source)
        elif args.command == "profile":
            receipt = _profile_command()
        elif args.command == "g1":
            receipt = _g1_command()
        elif args.command == "verify":
            receipt = _verify_work_package(args.wp)
        elif args.command == "batch":
            receipt = _batch_command(args.wps)
        else:
            _fail("ARGUMENT_ERROR", "a focused command is required")
        if receipt.get("status") != "PASS":
            failure = receipt.get("failure")
            if isinstance(failure, Mapping):
                _fail(str(failure.get("code", "WORKFLOW_FAILED")), str(failure.get("message", "workflow failed")))
            _fail("WORKFLOW_FAILED", "workflow did not return PASS")
        _print_success(receipt)
        return 0
    except WorkflowError as exc:
        _print_error(exc)
        return 1
    except Exception as exc:
        _print_error(WorkflowError("UNEXPECTED", f"{type(exc).__name__}: {exc}"))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
