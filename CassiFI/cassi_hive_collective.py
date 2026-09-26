"""Collective-intelligence control plane for Cassi Hive.

The base hive transports immutable capsules and reviewed bundles.  This module
adds the next layer: outcome-backed trust, cryptographic instance identity,
independence checks, weighted quorum, branching hypotheses, demand-driven
queries, diversity selection, specialist roles, safe program composition,
local adaptations, and time-aware consolidation.  It stores only semantic
control-plane artifacts; adaptive field tensors remain local to each owner.
"""
import hashlib
import hmac
import json
import math
import time
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from cassi_field_atlas import (
    FieldIntelligenceError,
    FieldProgram,
    Guard,
    PrimitiveStep,
    canonical_json_bytes,
    sha256_value,
)
from cassi_field_hive import ExperienceCapsule, Review
from cassi_hive_store import HiveStoreError, LocalHiveStore, make_document


COLLECTIVE_SCHEMA = "cassifi.hive.collective.v1"
IDENTITY_SCHEMA = "cassifi.hive.identity.v1"
OUTCOME_SCHEMA = "cassifi.hive.outcome.v1"
EXECUTION_ASSESSMENT_SCHEMA = "cassifi.hive.execution-assessment.v1"
REPUTATION_SCHEMA = "cassifi.hive.reputation.v1"
HYPOTHESIS_SCHEMA = "cassifi.hive.hypothesis.v1"
QUERY_SCHEMA = "cassifi.hive.query.v1"
OFFER_SCHEMA = "cassifi.hive.offer.v1"
ROLE_SCHEMA = "cassifi.hive.role.v1"
FORK_SCHEMA = "cassifi.hive.adaptation-fork.v1"
CONSOLIDATION_SCHEMA = "cassifi.hive.consolidation.v1"
EXPIRATION_SCHEMA = "cassifi.hive.expiration.v1"
COLLABORATION_REQUEST_SCHEMA = "cassifi.hive.collaboration-request.v1"
COLLABORATION_ASSIGNMENT_SCHEMA = "cassifi.hive.collaboration-assignment.v1"
COLLABORATION_RESPONSE_SCHEMA = "cassifi.hive.collaboration-response.v1"
REPRESENTATION_TRANSLATION_SCHEMA = "cassifi.hive.representation-translation.v1"
COLLECTIVE_SYNTHESIS_SCHEMA = "cassifi.hive.collective-synthesis.v1"
AFFECT_REPORT_SCHEMA = "cassifi.affect-report.v1"
METHOD_INTERFACE_SCHEMA = "cassifi.hive.method-interface.v1"
EXECUTABLE_METHOD_SCHEMA = "cassifi.hive.executable-method.v1"
METHOD_COMPOSITION_SCHEMA = "cassifi.hive.method-composition.v1"
METHOD_COMPOSITION_RESULT_SCHEMA = "cassifi.hive.method-composition-result.v1"


class CollectiveHiveError(ValueError):
    """Raised when a collective control-plane artifact is invalid."""


def _text(value: Any, label: str, *, limit: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > limit
        or any(ord(char) < 32 for char in value)
    ):
        raise CollectiveHiveError(f"{label} must be bounded nonempty text")
    return value


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise CollectiveHiveError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CollectiveHiveError(f"{label} must be a mapping")
    try:
        normalized = json.loads(canonical_json_bytes(value).decode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise CollectiveHiveError(f"{label} must be canonical JSON") from exc
    if not isinstance(normalized, dict):
        raise CollectiveHiveError(f"{label} must encode an object")
    return normalized


def _finite(value: Any, label: str, *, lower: float = 0.0, upper: float = 1.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CollectiveHiveError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < lower or result > upper:
        raise CollectiveHiveError(f"{label} must be finite and in [{lower}, {upper}]")
    return result


def _tuple_text(values: Sequence[Any], label: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise CollectiveHiveError(f"{label} must be a sequence")
    result = tuple(_text(value, label) for value in values)
    if len(result) != len(set(result)):
        raise CollectiveHiveError(f"{label} must not contain duplicates")
    return result

def _tuple_mapping(
    values: Sequence[Mapping[str, Any]], label: str,
) -> tuple[Mapping[str, Any], ...]:
    if isinstance(values, (str, bytes)):
        raise CollectiveHiveError(f"{label} must be a sequence")
    return tuple(_mapping(value, label) for value in values)


def _validate_method_value(value: Any, kind: str, label: str) -> None:
    valid = False
    if kind == "boolean":
        valid = isinstance(value, bool)
    elif kind == "integer":
        valid = isinstance(value, int) and not isinstance(value, bool)
    elif kind == "scalar":
        valid = (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        )
    elif kind == "text":
        valid = isinstance(value, str)
    elif kind == "vector":
        valid = (
            isinstance(value, Sequence)
            and not isinstance(value, (str, bytes))
            and all(
                isinstance(item, (int, float))
                and not isinstance(item, bool)
                and math.isfinite(float(item))
                for item in value
            )
        )
    elif kind == "mapping":
        valid = isinstance(value, Mapping)
    elif kind == "sequence":
        valid = isinstance(value, Sequence) and not isinstance(value, (str, bytes))
    elif kind == "json":
        try:
            canonical_json_bytes(value)
            valid = True
        except (TypeError, ValueError):
            valid = False
    if not valid:
        raise CollectiveHiveError(f"{label} does not satisfy method type {kind}")


def _key_digest(secret: bytes | bytearray | str) -> str:
    raw = secret.encode("utf-8") if isinstance(secret, str) else bytes(secret)
    if len(raw) < 16:
        raise CollectiveHiveError("identity signing key must contain at least 16 bytes")
    return hashlib.sha256(raw).hexdigest()


def _signature(payload: Mapping[str, Any], secret: bytes | bytearray | str) -> str:
    raw = secret.encode("utf-8") if isinstance(secret, str) else bytes(secret)
    return hmac.new(raw, canonical_json_bytes(payload), hashlib.sha256).hexdigest()


@dataclass(frozen=True, slots=True)
class InstanceIdentity:
    """Signed instance manifest used for provenance and anti-Sybil checks."""

    instance_id: str
    attestation_key_sha256: str
    source_identity_sha256: str
    configuration_sha256: str
    branch: str
    role: str
    parent_instance_id: str | None = None
    issued_ns: int = 0
    signature: str = ""

    def __post_init__(self) -> None:
        _text(self.instance_id, "instance_id")
        _digest(self.attestation_key_sha256, "attestation_key_sha256")
        _digest(self.source_identity_sha256, "source_identity_sha256")
        _digest(self.configuration_sha256, "configuration_sha256")
        _text(self.branch, "branch")
        _text(self.role, "role")
        if self.parent_instance_id is not None:
            _text(self.parent_instance_id, "parent_instance_id")
        if isinstance(self.issued_ns, bool) or not isinstance(self.issued_ns, int) or self.issued_ns < 0:
            raise CollectiveHiveError("issued_ns must be a nonnegative integer")
        if self.signature:
            _digest(self.signature, "identity signature")

    @property
    def payload(self) -> Mapping[str, Any]:
        return {
            "attestation_key_sha256": self.attestation_key_sha256,
            "branch": self.branch,
            "configuration_sha256": self.configuration_sha256,
            "instance_id": self.instance_id,
            "issued_ns": self.issued_ns,
            "parent_instance_id": self.parent_instance_id,
            "role": self.role,
            "source_identity_sha256": self.source_identity_sha256,
        }

    @property
    def object_id(self) -> str:
        return sha256_value(
            {
                "schema": IDENTITY_SCHEMA,
                "content": {"payload": self.payload, "signature": self.signature},
            }
        )

    @classmethod
    def issue(
        cls,
        *,
        instance_id: str,
        secret: bytes | bytearray | str,
        source_identity_sha256: str,
        configuration_sha256: str,
        branch: str = "main",
        role: str = "worker",
        parent_instance_id: str | None = None,
        issued_ns: int | None = None,
    ) -> "InstanceIdentity":
        manifest = cls(
            instance_id=instance_id,
            attestation_key_sha256=_key_digest(secret),
            source_identity_sha256=source_identity_sha256,
            configuration_sha256=configuration_sha256,
            branch=branch,
            role=role,
            parent_instance_id=parent_instance_id,
            issued_ns=time.time_ns() if issued_ns is None else issued_ns,
        )
        return replace(manifest, signature=_signature(manifest.payload, secret))

    def verify(self, secret: bytes | bytearray | str) -> bool:
        try:
            return hmac.compare_digest(
                self.attestation_key_sha256,
                _key_digest(secret),
            ) and hmac.compare_digest(self.signature, _signature(self.payload, secret))
        except CollectiveHiveError:
            return False

    def as_dict(self) -> Mapping[str, Any]:
        return make_document(
            IDENTITY_SCHEMA,
            {"payload": dict(self.payload), "signature": self.signature},
        )


@dataclass(frozen=True, slots=True)
class IndependenceReport:
    accepted_reviewer_ids: tuple[str, ...]
    rejected_reviewer_ids: tuple[str, ...]
    reasons: Mapping[str, str]
    independence_groups: tuple[tuple[str, ...], ...]

    @property
    def independent_count(self) -> int:
        return len(self.accepted_reviewer_ids)

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "accepted_reviewer_ids": list(self.accepted_reviewer_ids),
            "independence_groups": [list(group) for group in self.independence_groups],
            "reasons": dict(self.reasons),
            "rejected_reviewer_ids": list(self.rejected_reviewer_ids),
            "schema": COLLECTIVE_SCHEMA + ".independence",
        }
def check_reviewer_independence(
    reviewer_ids: Sequence[str],
    identities: Mapping[str, InstanceIdentity],
    *,
    origin_instance_ids: Sequence[str] = (),
) -> IndependenceReport:
    """Reject reviewers sharing an attestation, lineage, source, or config."""

    origins = set(origin_instance_ids)
    reviewer_sequence = _tuple_text(reviewer_ids, "reviewer_id")
    reviewer_set = set(reviewer_sequence)
    accepted: list[str] = []
    rejected: list[str] = []
    reasons: dict[str, str] = {}
    used_parents: set[str] = set()
    groups: dict[tuple[str, str, str, str], list[str]] = {}
    seen_reviewers: set[str] = set()
    for reviewer_id in reviewer_sequence:
        if reviewer_id in seen_reviewers:
            continue
        seen_reviewers.add(reviewer_id)
        identity = identities.get(reviewer_id)
        if identity is None:
            rejected.append(reviewer_id)
            reasons[reviewer_id] = "missing-identity"
            continue
        if reviewer_id in origins:
            rejected.append(reviewer_id)
            reasons[reviewer_id] = "origin-cannot-review"
            continue
        if identity.parent_instance_id and (
            identity.parent_instance_id in reviewer_set
            or identity.parent_instance_id in used_parents
        ):
            rejected.append(reviewer_id)
            reasons[reviewer_id] = "shared-identity-lineage-or-configuration"
            continue
        if identity.parent_instance_id:
            used_parents.add(identity.parent_instance_id)
        group_key = (
            identity.attestation_key_sha256,
            identity.source_identity_sha256,
            identity.configuration_sha256,
            identity.parent_instance_id or "",
        )
        prior = groups.get(group_key)
        if prior:
            rejected.append(reviewer_id)
            reasons[reviewer_id] = "shared-identity-lineage-or-configuration"
            prior.append(reviewer_id)
            continue
        groups[group_key] = [reviewer_id]
        accepted.append(reviewer_id)
    return IndependenceReport(
        accepted_reviewer_ids=tuple(accepted),
        rejected_reviewer_ids=tuple(rejected),
        reasons=reasons,
        independence_groups=tuple(tuple(group) for group in groups.values()),
    )


@dataclass(frozen=True, slots=True)
class OutcomeMetric:
    name: str
    baseline: float
    control: float
    post: float
    higher_is_better: bool = True

    def __post_init__(self) -> None:
        _text(self.name, "metric name")
        for label, value in (("baseline", self.baseline), ("control", self.control), ("post", self.post)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise CollectiveHiveError(f"metric {label} must be finite")
        if not isinstance(self.higher_is_better, bool):
            raise CollectiveHiveError("higher_is_better must be Boolean")

    @property
    def score(self) -> float:
        denominator = abs(float(self.control) - float(self.baseline))
        if denominator <= 1e-12:
            if abs(float(self.post) - float(self.baseline)) <= 1e-12:
                return 0.5
            improved = (
                float(self.post) > float(self.baseline)
                if self.higher_is_better
                else float(self.post) < float(self.baseline)
            )
            return 1.0 if improved else 0.0
        signed_progress = (float(self.post) - float(self.baseline)) / (float(self.control) - float(self.baseline))
        if not self.higher_is_better:
            signed_progress = -signed_progress
        return max(0.0, min(1.0, signed_progress))

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "baseline": self.baseline,
            "control": self.control,
            "higher_is_better": self.higher_is_better,
            "name": self.name,
            "post": self.post,
            "score": self.score,
        }

@dataclass(frozen=True, slots=True)
class ExecutionAssessment:
    """Immutable evaluator result bound to actual trace documents."""

    bundle_id: str
    recipient_instance_id: str
    adoption_receipt_id: str
    protocol_sha256: str
    evaluator_id: str
    evaluator_version: str
    trace_document_ids: tuple[str, ...]
    metrics: tuple[OutcomeMetric, ...]
    held_out: bool
    scoring_rule: str
    failure_modes: tuple[str, ...] = ()
    observed_ns: int = 0
    valid_until_ns: int | None = None

    def __post_init__(self) -> None:
        _digest(self.bundle_id, "assessment bundle_id")
        _text(self.recipient_instance_id, "assessment recipient_instance_id")
        _digest(self.adoption_receipt_id, "assessment adoption_receipt_id")
        _digest(self.protocol_sha256, "assessment protocol_sha256")
        _text(self.evaluator_id, "assessment evaluator_id")
        _text(self.evaluator_version, "assessment evaluator_version")
        _text(self.scoring_rule, "assessment scoring_rule")
        trace_ids = tuple(self.trace_document_ids)
        if not trace_ids:
            raise CollectiveHiveError(
                "execution assessment needs at least one trace document"
            )
        for trace_id in trace_ids:
            _digest(trace_id, "assessment trace document")
        if len(trace_ids) != len(set(trace_ids)):
            raise CollectiveHiveError(
                "execution assessment trace documents must be unique"
            )
        object.__setattr__(self, "trace_document_ids", trace_ids)
        metrics = tuple(self.metrics)
        if not metrics or any(
            not isinstance(metric, OutcomeMetric) for metric in metrics
        ):
            raise CollectiveHiveError(
                "execution assessment needs OutcomeMetric values"
            )
        names = tuple(metric.name for metric in metrics)
        if len(names) != len(set(names)):
            raise CollectiveHiveError(
                "execution assessment metric names must be unique"
            )
        object.__setattr__(self, "metrics", metrics)
        if not isinstance(self.held_out, bool):
            raise CollectiveHiveError("assessment held_out must be Boolean")
        object.__setattr__(
            self,
            "failure_modes",
            _tuple_text(self.failure_modes, "assessment failure mode"),
        )
        if (
            isinstance(self.observed_ns, bool)
            or not isinstance(self.observed_ns, int)
            or self.observed_ns < 0
        ):
            raise CollectiveHiveError(
                "assessment observed_ns must be nonnegative"
            )
        if self.valid_until_ns is not None:
            if (
                isinstance(self.valid_until_ns, bool)
                or not isinstance(self.valid_until_ns, int)
                or self.valid_until_ns < self.observed_ns
            ):
                raise CollectiveHiveError(
                    "assessment valid_until_ns is invalid"
                )

    @property
    def object_id(self) -> str:
        return sha256_value(
            {"schema": EXECUTION_ASSESSMENT_SCHEMA, "content": self.as_dict()}
        )

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "adoption_receipt_id": self.adoption_receipt_id,
            "bundle_id": self.bundle_id,
            "evaluator_id": self.evaluator_id,
            "evaluator_version": self.evaluator_version,
            "failure_modes": list(self.failure_modes),
            "held_out": self.held_out,
            "metrics": [metric.as_dict() for metric in self.metrics],
            "observed_ns": self.observed_ns,
            "protocol_sha256": self.protocol_sha256,
            "recipient_instance_id": self.recipient_instance_id,
            "scoring_rule": self.scoring_rule,
            "trace_document_ids": list(self.trace_document_ids),
            "valid_until_ns": self.valid_until_ns,
        }

    def document(self) -> Mapping[str, Any]:
        return make_document(EXECUTION_ASSESSMENT_SCHEMA, self.as_dict())

    @classmethod
    def from_document(
        cls, document: Mapping[str, Any]
    ) -> "ExecutionAssessment":
        if (
            not isinstance(document, Mapping)
            or document.get("schema") != EXECUTION_ASSESSMENT_SCHEMA
            or not isinstance(document.get("content"), Mapping)
        ):
            raise CollectiveHiveError(
                "execution assessment document is invalid"
            )
        content = document["content"]
        raw_metrics = content.get("metrics")
        if not isinstance(raw_metrics, list):
            raise CollectiveHiveError(
                "execution assessment metrics are invalid"
            )
        try:
            metrics = tuple(
                OutcomeMetric(
                    name=metric["name"],
                    baseline=metric["baseline"],
                    control=metric["control"],
                    post=metric["post"],
                    higher_is_better=metric.get(
                        "higher_is_better", True
                    ),
                )
                for metric in raw_metrics
                if isinstance(metric, Mapping)
            )
            if len(metrics) != len(raw_metrics):
                raise CollectiveHiveError(
                    "execution assessment metric row is invalid"
                )
            return cls(
                bundle_id=content["bundle_id"],
                recipient_instance_id=content["recipient_instance_id"],
                adoption_receipt_id=content["adoption_receipt_id"],
                protocol_sha256=content["protocol_sha256"],
                evaluator_id=content["evaluator_id"],
                evaluator_version=content["evaluator_version"],
                trace_document_ids=tuple(content["trace_document_ids"]),
                metrics=metrics,
                held_out=content["held_out"],
                scoring_rule=content["scoring_rule"],
                failure_modes=tuple(content.get("failure_modes", ())),
                observed_ns=content.get("observed_ns", 0),
                valid_until_ns=content.get("valid_until_ns"),
            )
        except (KeyError, TypeError) as exc:
            raise CollectiveHiveError(
                "execution assessment content is malformed"
            ) from exc



@dataclass(frozen=True, slots=True)
class OutcomeEvidence:
    bundle_id: str
    recipient_instance_id: str
    adoption_receipt_id: str
    protocol_sha256: str
    metrics: tuple[OutcomeMetric, ...]
    held_out: bool
    failure_modes: tuple[str, ...] = ()
    observed_ns: int = 0
    valid_until_ns: int | None = None
    execution_assessment_id: str | None = None
    trace_document_ids: tuple[str, ...] = ()
    evaluator_id: str | None = None
    evaluator_version: str | None = None
    scoring_rule: str | None = None

    def __post_init__(self) -> None:
        _digest(self.bundle_id, "bundle_id")
        _text(self.recipient_instance_id, "recipient_instance_id")
        _digest(self.adoption_receipt_id, "adoption_receipt_id")
        _digest(self.protocol_sha256, "protocol_sha256")
        if not self.metrics:
            raise CollectiveHiveError("outcome evidence needs at least one metric")
        object.__setattr__(self, "metrics", tuple(self.metrics))
        if any(not isinstance(metric, OutcomeMetric) for metric in self.metrics):
            raise CollectiveHiveError("outcome metrics must be OutcomeMetric values")
        if not isinstance(self.held_out, bool):
            raise CollectiveHiveError("held_out must be Boolean")
        object.__setattr__(self, "failure_modes", _tuple_text(self.failure_modes, "failure mode"))
        if isinstance(self.observed_ns, bool) or not isinstance(self.observed_ns, int) or self.observed_ns < 0:
            raise CollectiveHiveError("observed_ns must be nonnegative")
        if self.valid_until_ns is not None:
            if isinstance(self.valid_until_ns, bool) or not isinstance(self.valid_until_ns, int):
                raise CollectiveHiveError("valid_until_ns must be an integer")
            if self.valid_until_ns < self.observed_ns:
                raise CollectiveHiveError("valid_until_ns precedes observation")
        trace_ids = tuple(self.trace_document_ids)
        for trace_id in trace_ids:
            _digest(trace_id, "outcome trace document")
        if len(trace_ids) != len(set(trace_ids)):
            raise CollectiveHiveError(
                "outcome trace documents must be unique"
            )
        object.__setattr__(self, "trace_document_ids", trace_ids)
        if self.execution_assessment_id is not None:
            _digest(
                self.execution_assessment_id,
                "execution_assessment_id",
            )
            if not trace_ids:
                raise CollectiveHiveError(
                    "execution-backed outcome needs trace documents"
                )
            for label, value in (
                ("evaluator_id", self.evaluator_id),
                ("evaluator_version", self.evaluator_version),
                ("scoring_rule", self.scoring_rule),
            ):
                _text(value, label)
        elif any(
            value is not None
            for value in (
                self.evaluator_id,
                self.evaluator_version,
                self.scoring_rule,
            )
        ) or trace_ids:
            raise CollectiveHiveError(
                "outcome evaluator metadata needs an execution assessment"
            )

    @property
    def score(self) -> float:
        return sum(metric.score for metric in self.metrics) / len(self.metrics)

    @property
    def success(self) -> bool:
        return self.score >= 0.5 and not self.failure_modes

    @property
    def object_id(self) -> str:
        return sha256_value({"schema": OUTCOME_SCHEMA, "content": self.as_dict()})

    def expired(self, *, now_ns: int | None = None) -> bool:
        return self.valid_until_ns is not None and (time.time_ns() if now_ns is None else now_ns) > self.valid_until_ns

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "adoption_receipt_id": self.adoption_receipt_id,
            "bundle_id": self.bundle_id,
            "evaluator_id": self.evaluator_id,
            "evaluator_version": self.evaluator_version,
            "execution_assessment_id": self.execution_assessment_id,
            "failure_modes": list(self.failure_modes),
            "held_out": self.held_out,
            "metrics": [metric.as_dict() for metric in self.metrics],
            "observed_ns": self.observed_ns,
            "protocol_sha256": self.protocol_sha256,
            "recipient_instance_id": self.recipient_instance_id,
            "score": self.score,
            "success": self.success,
            "scoring_rule": self.scoring_rule,
            "trace_document_ids": list(self.trace_document_ids),
            "valid_until_ns": self.valid_until_ns,
        }

    def document(self) -> Mapping[str, Any]:
        return make_document(OUTCOME_SCHEMA, self.as_dict())


POPULATION_ROLLOUT_SCHEMA = "cassifi.hive.population-rollout.v1"


@dataclass(frozen=True, slots=True)
class PopulationMemberOutcome:
    """One member's adoption and held-out result in a population rollout."""

    instance_id: str
    field_profile_sha256: str
    adoption_status: str
    outcome_success: bool | None
    score: float | None
    adoption_receipt_id: str | None = None
    outcome_id: str | None = None
    adopted_program_ids: tuple[str, ...] = ()
    post_state_sha256: str | None = None
    report: Mapping[str, Any] = ()
    error: str | None = None
    held_out: bool = True

    def __post_init__(self) -> None:
        _text(self.instance_id, "population member instance_id")
        _digest(self.field_profile_sha256, "population member field profile")
        if self.adoption_status not in {"accepted", "replayed", "failed"}:
            raise CollectiveHiveError("population member adoption status is unsupported")
        if self.outcome_success is not None and not isinstance(self.outcome_success, bool):
            raise CollectiveHiveError("population member outcome_success must be Boolean or None")
        if self.score is not None:
            _finite(self.score, "population member score")
        if self.adoption_status == "failed":
            if self.outcome_success is not None or self.score is not None:
                raise CollectiveHiveError("failed adoption cannot contain an outcome")
            if not self.error:
                raise CollectiveHiveError("failed adoption needs an error")
        else:
            if self.outcome_success is None or self.score is None:
                raise CollectiveHiveError("completed adoption needs an outcome")
            if self.adoption_receipt_id is None or self.outcome_id is None:
                raise CollectiveHiveError("completed adoption needs receipt and outcome IDs")
            _digest(self.adoption_receipt_id, "population adoption receipt")
            _digest(self.outcome_id, "population outcome")
        if self.adoption_receipt_id is not None and self.adoption_status == "failed":
            _digest(self.adoption_receipt_id, "population adoption receipt")
        if self.outcome_id is not None and self.adoption_status == "failed":
            _digest(self.outcome_id, "population outcome")
        if self.post_state_sha256 is not None:
            _digest(self.post_state_sha256, "population post state")
        object.__setattr__(self, "adopted_program_ids", _tuple_text(self.adopted_program_ids, "population program"))
        raw_report = {} if self.report == () else self.report
        object.__setattr__(self, "report", _mapping(raw_report, "population adoption report"))
        if self.error is not None:
            _text(self.error, "population adoption error")
        if not isinstance(self.held_out, bool):
            raise CollectiveHiveError("population held_out must be Boolean")

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "adopted_program_ids": list(self.adopted_program_ids),
            "adoption_receipt_id": self.adoption_receipt_id,
            "adoption_status": self.adoption_status,
            "error": self.error,
            "field_profile_sha256": self.field_profile_sha256,
            "held_out": self.held_out,
            "instance_id": self.instance_id,
            "outcome_id": self.outcome_id,
            "outcome_success": self.outcome_success,
            "post_state_sha256": self.post_state_sha256,
            "report": dict(self.report),
            "score": self.score,
        }


@dataclass(frozen=True, slots=True)
class PopulationOutcomeLedger:
    """Content-addressed population receipt for one bundle rollout."""

    bundle_id: str
    protocol_sha256: str
    members: tuple[PopulationMemberOutcome, ...]
    held_out: bool = True
    created_ns: int = 0

    def __post_init__(self) -> None:
        _digest(self.bundle_id, "population bundle_id")
        _digest(self.protocol_sha256, "population protocol_sha256")
        if not self.members:
            raise CollectiveHiveError("population rollout needs at least one member")
        object.__setattr__(self, "members", tuple(self.members))
        if any(not isinstance(member, PopulationMemberOutcome) for member in self.members):
            raise CollectiveHiveError("population members must be PopulationMemberOutcome values")
        instance_ids = tuple(member.instance_id for member in self.members)
        if len(instance_ids) != len(set(instance_ids)):
            raise CollectiveHiveError("population member instance IDs must be unique")
        profiles = tuple(member.field_profile_sha256 for member in self.members)
        if len(profiles) != len(set(profiles)):
            raise CollectiveHiveError("population member field profiles must be distinct")
        if any(member.held_out != self.held_out for member in self.members):
            raise CollectiveHiveError("population held-out settings must agree")
        if isinstance(self.created_ns, bool) or not isinstance(self.created_ns, int) or self.created_ns < 0:
            raise CollectiveHiveError("population created_ns must be nonnegative")

    @property
    def object_id(self) -> str:
        return sha256_value({"schema": POPULATION_ROLLOUT_SCHEMA, "content": self.as_dict()})

    @property
    def member_count(self) -> int:
        return len(self.members)

    @property
    def adopted_count(self) -> int:
        return sum(member.adoption_status in {"accepted", "replayed"} for member in self.members)

    @property
    def failed_adoption_count(self) -> int:
        return sum(member.adoption_status == "failed" for member in self.members)

    @property
    def successful_outcome_count(self) -> int:
        return sum(member.outcome_success is True for member in self.members)

    @property
    def population_score(self) -> float | None:
        scores = [member.score for member in self.members if member.score is not None]
        return None if not scores else sum(scores) / len(scores)

    @property
    def outcome_coverage(self) -> float:
        return sum(member.score is not None for member in self.members) / self.member_count

    @property
    def status(self) -> str:
        if self.successful_outcome_count == self.member_count:
            return "accepted"
        if self.successful_outcome_count:
            return "partial"
        return "failed"

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "adopted_count": self.adopted_count,
            "bundle_id": self.bundle_id,
            "created_ns": self.created_ns,
            "failed_adoption_count": self.failed_adoption_count,
            "held_out": self.held_out,
            "member_count": self.member_count,
            "members": [member.as_dict() for member in self.members],
            "outcome_coverage": self.outcome_coverage,
            "population_score": self.population_score,
            "protocol_sha256": self.protocol_sha256,
            "status": self.status,
            "successful_outcome_count": self.successful_outcome_count,
        }

    def document(self) -> Mapping[str, Any]:
        return make_document(POPULATION_ROLLOUT_SCHEMA, self.as_dict())

POPULATION_ROUNDS_SCHEMA = "cassifi.hive.population-rounds.v1"


@dataclass(frozen=True, slots=True)
class PopulationMemberComparison:
    """One member's local score versus the population and prior round."""

    instance_id: str
    local_score: float | None
    population_score: float | None
    local_minus_population: float | None
    previous_local_score: float | None = None
    local_score_delta: float | None = None
    population_score_delta: float | None = None
    outcome_success: bool | None = None

    def __post_init__(self) -> None:
        _text(self.instance_id, "round comparison instance_id")
        for label, value in (
            ("local_score", self.local_score),
            ("population_score", self.population_score),
            ("local_minus_population", self.local_minus_population),
            ("previous_local_score", self.previous_local_score),
            ("local_score_delta", self.local_score_delta),
            ("population_score_delta", self.population_score_delta),
        ):
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                    raise CollectiveHiveError(f"{label} must be finite or None")
        if self.outcome_success is not None and not isinstance(self.outcome_success, bool):
            raise CollectiveHiveError("round comparison outcome_success must be Boolean or None")

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "instance_id": self.instance_id,
            "local_minus_population": self.local_minus_population,
            "local_score": self.local_score,
            "local_score_delta": self.local_score_delta,
            "outcome_success": self.outcome_success,
            "population_score": self.population_score,
            "population_score_delta": self.population_score_delta,
            "previous_local_score": self.previous_local_score,
        }


@dataclass(frozen=True, slots=True)
class PopulationRoundRecord:
    """Persisted summary of one successive population rollout round."""

    round_index: int
    bundle_id: str
    protocol_sha256: str
    population_ledger_id: str
    status: str
    population_score: float | None
    outcome_coverage: float
    comparisons: tuple[PopulationMemberComparison, ...]
    calibrated_reviewer_ids: tuple[str, ...] = ()
    reviewer_predictions: Mapping[str, float] = ()
    outcome_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.round_index, bool) or not isinstance(self.round_index, int) or self.round_index < 0:
            raise CollectiveHiveError("round_index must be a nonnegative integer")
        _digest(self.bundle_id, "round bundle_id")
        _digest(self.protocol_sha256, "round protocol_sha256")
        _digest(self.population_ledger_id, "round population ledger")
        if self.status not in {"accepted", "partial", "failed"}:
            raise CollectiveHiveError("round status is unsupported")
        if self.population_score is not None:
            _finite(self.population_score, "round population_score")
        _finite(self.outcome_coverage, "round outcome_coverage")
        if not self.comparisons:
            raise CollectiveHiveError("round needs member comparisons")
        object.__setattr__(self, "comparisons", tuple(self.comparisons))
        if any(not isinstance(item, PopulationMemberComparison) for item in self.comparisons):
            raise CollectiveHiveError("round comparisons must be PopulationMemberComparison values")
        instance_ids = tuple(item.instance_id for item in self.comparisons)
        if len(instance_ids) != len(set(instance_ids)):
            raise CollectiveHiveError("round comparison instance IDs must be unique")
        object.__setattr__(self, "calibrated_reviewer_ids", _tuple_text(self.calibrated_reviewer_ids, "round calibrated reviewer"))
        raw_predictions = {} if self.reviewer_predictions == () else self.reviewer_predictions
        predictions = _mapping(raw_predictions, "round reviewer predictions")
        for reviewer_id, value in predictions.items():
            _text(reviewer_id, "round reviewer ID")
            _finite(value, "round reviewer prediction")
        object.__setattr__(self, "reviewer_predictions", predictions)
        if isinstance(self.outcome_ids, (str, bytes)):
            raise CollectiveHiveError("round outcome IDs must be a sequence")
        outcome_ids = tuple(_digest(item, "round outcome ID") for item in self.outcome_ids)
        object.__setattr__(self, "outcome_ids", outcome_ids)

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "calibrated_reviewer_ids": list(self.calibrated_reviewer_ids),
            "comparisons": [item.as_dict() for item in self.comparisons],
            "outcome_coverage": self.outcome_coverage,
            "outcome_ids": list(self.outcome_ids),
            "population_ledger_id": self.population_ledger_id,
            "population_score": self.population_score,
            "protocol_sha256": self.protocol_sha256,
            "reviewer_predictions": dict(self.reviewer_predictions),
            "round_index": self.round_index,
            "status": self.status,
        }

@dataclass(frozen=True, slots=True)
class PopulationRoundLedger:
    """Content-addressed comparison ledger across successive bundle rounds."""

    rounds: tuple[PopulationRoundRecord, ...]
    created_ns: int = 0

    def __post_init__(self) -> None:
        if not self.rounds:
            raise CollectiveHiveError("round ledger needs at least one round")
        object.__setattr__(self, "rounds", tuple(self.rounds))
        if any(not isinstance(item, PopulationRoundRecord) for item in self.rounds):
            raise CollectiveHiveError("rounds must be PopulationRoundRecord values")
        indices = tuple(item.round_index for item in self.rounds)
        if indices != tuple(range(len(indices))):
            raise CollectiveHiveError("round indexes must be contiguous from zero")
        bundle_ids = tuple(item.bundle_id for item in self.rounds)
        if len(bundle_ids) != len(set(bundle_ids)):
            raise CollectiveHiveError("round bundle IDs must be unique")
        if isinstance(self.created_ns, bool) or not isinstance(self.created_ns, int) or self.created_ns < 0:
            raise CollectiveHiveError("round ledger created_ns must be nonnegative")

    @property
    def object_id(self) -> str:
        return sha256_value({"schema": POPULATION_ROUNDS_SCHEMA, "content": self.as_dict()})

    @property
    def round_count(self) -> int:
        return len(self.rounds)

    @property
    def status(self) -> str:
        accepted = sum(item.status == "accepted" for item in self.rounds)
        if accepted == self.round_count:
            return "accepted"
        if accepted:
            return "partial"
        return "failed"

    @property
    def final_population_score(self) -> float | None:
        return self.rounds[-1].population_score

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "created_ns": self.created_ns,
            "final_population_score": self.final_population_score,
            "round_count": self.round_count,
            "rounds": [item.as_dict() for item in self.rounds],
            "status": self.status,
        }

    def document(self) -> Mapping[str, Any]:
        return make_document(POPULATION_ROUNDS_SCHEMA, self.as_dict())

@dataclass(frozen=True, slots=True)
class ReviewerProfile:
    reviewer_instance_id: str
    identity_key_sha256: str
    review_count: int = 0
    correct_count: int = 0
    brier_loss: float = 0.0
    independent_count: int = 0
    last_evaluated_ns: int = 0
    domains: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.reviewer_instance_id, "reviewer_instance_id")
        _digest(self.identity_key_sha256, "identity_key_sha256")
        for label, value in (("review_count", self.review_count), ("correct_count", self.correct_count), ("independent_count", self.independent_count)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise CollectiveHiveError(f"{label} must be nonnegative")
        if self.correct_count > self.review_count:
            raise CollectiveHiveError("correct_count exceeds review_count")
        _finite(self.brier_loss, "brier_loss", upper=1.0)
        object.__setattr__(self, "domains", _tuple_text(self.domains, "reviewer domain"))

    @property
    def reliability(self) -> float:
        return (self.correct_count + 1.0) / (self.review_count + 2.0)

    @property
    def calibration(self) -> float:
        return max(0.0, 1.0 - self.brier_loss)

    @property
    def weight(self) -> float:
        return self.reliability * self.calibration

    @classmethod
    def virgin(cls, reviewer_instance_id: str, identity_key_sha256: str) -> "ReviewerProfile":
        return cls(reviewer_instance_id=reviewer_instance_id, identity_key_sha256=identity_key_sha256)

    def evaluate(self, predicted_support: float, actual_success: bool, *, independent: bool = True) -> "ReviewerProfile":
        prediction = _finite(predicted_support, "predicted_support")
        target = 1.0 if actual_success else 0.0
        return replace(
            self,
            review_count=self.review_count + 1,
            correct_count=self.correct_count + int((prediction >= 0.5) == actual_success),
            brier_loss=(self.brier_loss * self.review_count + (prediction - target) ** 2) / (self.review_count + 1),
            independent_count=self.independent_count + int(independent),
            last_evaluated_ns=time.time_ns(),
        )

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "brier_loss": self.brier_loss,
            "calibration": self.calibration,
            "correct_count": self.correct_count,
            "domains": list(self.domains),
            "identity_key_sha256": self.identity_key_sha256,
            "independent_count": self.independent_count,
            "last_evaluated_ns": self.last_evaluated_ns,
            "reliability": self.reliability,
            "review_count": self.review_count,
            "reviewer_instance_id": self.reviewer_instance_id,
            "weight": self.weight,
        }


class ReputationLedger:
    """Persistent reviewer calibration ledger backed by immutable documents."""

    def __init__(self, store: LocalHiveStore) -> None:
        if not isinstance(store, LocalHiveStore):
            raise CollectiveHiveError("reputation ledger requires LocalHiveStore")
        self.store = store

    def save(self, profile: ReviewerProfile) -> str:
        return self.store.put_document(make_document(REPUTATION_SCHEMA, profile.as_dict()))

    def load(self, reviewer_instance_id: str) -> ReviewerProfile | None:
        _text(reviewer_instance_id, "reviewer_instance_id")
        rows = self.store.list_documents(schema=REPUTATION_SCHEMA)
        matches = [
            row["content"]
            for row in rows
            if row.get("content", {}).get("reviewer_instance_id") == reviewer_instance_id
        ]
        if not matches:
            return None
        content = matches[-1]
        return ReviewerProfile(
            reviewer_instance_id=content["reviewer_instance_id"],
            identity_key_sha256=content["identity_key_sha256"],
            review_count=content["review_count"],
            correct_count=content["correct_count"],
            brier_loss=content["brier_loss"],
            independent_count=content["independent_count"],
            last_evaluated_ns=content["last_evaluated_ns"],
            domains=tuple(content.get("domains", ())),
        )

    def update(
        self,
        profile: ReviewerProfile,
        *,
        predicted_support: float,
        actual_success: bool,
        independent: bool = True,
    ) -> ReviewerProfile:
        updated = profile.evaluate(
            predicted_support,
            actual_success,
            independent=independent,
        )
        self.save(updated)
        return updated

    def calibrate_outcome(
        self,
        profiles: Mapping[str, ReviewerProfile],
        *,
        predicted_support: Mapping[str, float],
        actual_success: bool,
        independent_ids: Sequence[str] = (),
    ) -> Mapping[str, ReviewerProfile]:
        independent = set(independent_ids)
        updated: dict[str, ReviewerProfile] = {}
        for reviewer_id, prediction in predicted_support.items():
            profile = profiles.get(reviewer_id) or self.load(reviewer_id)
            if profile is None:
                continue
            updated[reviewer_id] = self.update(
                profile,
                predicted_support=prediction,
                actual_success=actual_success,
                independent=reviewer_id in independent,
            )
        return updated


@dataclass(frozen=True, slots=True)
class QuorumReport:
    accepted: bool
    support_weight: float
    refute_weight: float
    accepted_reviewer_ids: tuple[str, ...]
    rejected_reviewer_ids: tuple[str, ...]
    reasons: Mapping[str, str]
    minimum_support_weight: float
    minimum_independent_reviewers: int

    @property
    def margin(self) -> float:
        return self.support_weight - self.refute_weight

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "accepted": self.accepted,
            "accepted_reviewer_ids": list(self.accepted_reviewer_ids),
            "margin": self.margin,
            "minimum_independent_reviewers": self.minimum_independent_reviewers,
            "minimum_support_weight": self.minimum_support_weight,
            "reasons": dict(self.reasons),
            "rejected_reviewer_ids": list(self.rejected_reviewer_ids),
            "refute_weight": self.refute_weight,
            "support_weight": self.support_weight,
        }


def weighted_quorum(
    reviews: Sequence[Review],
    profiles: Mapping[str, ReviewerProfile],
    identities: Mapping[str, InstanceIdentity],
    *,
    origin_instance_ids: Sequence[str] = (),
    minimum_support_weight: float = 1.0,
    minimum_independent_reviewers: int = 2,
    minimum_margin: float = 0.0,
) -> QuorumReport:
    if minimum_support_weight <= 0 or minimum_independent_reviewers < 1:
        raise CollectiveHiveError("quorum thresholds must be positive")
    review_ids = tuple(review.reviewer_instance_id for review in reviews)
    independence = check_reviewer_independence(
        review_ids,
        identities,
        origin_instance_ids=origin_instance_ids,
    )
    accepted_set = set(independence.accepted_reviewer_ids)
    effective_ids: list[str] = []
    support = 0.0
    refute = 0.0
    reasons = dict(independence.reasons)
    rejected_ids = list(independence.rejected_reviewer_ids)
    counted_ids: set[str] = set()
    for review in reviews:
        reviewer_id = review.reviewer_instance_id
        if reviewer_id not in accepted_set or reviewer_id in counted_ids:
            continue
        counted_ids.add(reviewer_id)
        profile = profiles.get(reviewer_id)
        if profile is None:
            reasons[reviewer_id] = "missing-reputation-profile"
            rejected_ids.append(reviewer_id)
            continue
        if review.result == "inconclusive":
            reasons[reviewer_id] = "inconclusive"
            rejected_ids.append(reviewer_id)
            continue
        effective_ids.append(reviewer_id)
        weight = profile.weight
        if review.result == "supports":
            support += weight
        elif review.result == "refutes":
            refute += weight
    accepted = (
        len(effective_ids) >= minimum_independent_reviewers
        and support >= minimum_support_weight
        and support - refute >= minimum_margin
        and refute == 0.0
    )
    return QuorumReport(
        accepted=accepted,
        support_weight=support,
        refute_weight=refute,
        accepted_reviewer_ids=tuple(effective_ids),
        rejected_reviewer_ids=tuple(dict.fromkeys(rejected_ids)),
        reasons=reasons,
        minimum_support_weight=minimum_support_weight,
        minimum_independent_reviewers=minimum_independent_reviewers,
    )


@dataclass(frozen=True, slots=True)
class HypothesisNode:
    hypothesis_id: str
    candidate_id: str
    branch_id: str
    parent_hypothesis_id: str | None
    domain: str
    status: str = "active"
    valid_until_ns: int | None = None

    def __post_init__(self) -> None:
        for label, value in (("hypothesis_id", self.hypothesis_id), ("candidate_id", self.candidate_id), ("branch_id", self.branch_id), ("domain", self.domain)):
            _text(value, label)
        if self.parent_hypothesis_id is not None:
            _text(self.parent_hypothesis_id, "parent_hypothesis_id")
        if self.status not in {"active", "refuted", "superseded", "conditional", "expired"}:
            raise CollectiveHiveError("hypothesis status is unsupported")

    @property
    def expired(self) -> bool:
        return self.valid_until_ns is not None and time.time_ns() > self.valid_until_ns

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "branch_id": self.branch_id,
            "candidate_id": self.candidate_id,
            "domain": self.domain,
            "hypothesis_id": self.hypothesis_id,
            "parent_hypothesis_id": self.parent_hypothesis_id,
            "status": "expired" if self.expired else self.status,
            "valid_until_ns": self.valid_until_ns,
        }


@dataclass(frozen=True, slots=True)
class HypothesisEdge:
    source_hypothesis_id: str
    target_hypothesis_id: str
    relation: str
    condition: Mapping[str, Any] = ()

    def __post_init__(self) -> None:
        _text(self.source_hypothesis_id, "source_hypothesis_id")
        _text(self.target_hypothesis_id, "target_hypothesis_id")
        if self.relation not in {"supports", "contradicts", "supersedes", "conditional-on", "specializes"}:
            raise CollectiveHiveError("hypothesis relation is unsupported")
        object.__setattr__(self, "condition", {} if self.condition == () else _mapping(self.condition, "edge condition"))

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "condition": dict(self.condition),
            "relation": self.relation,
            "source_hypothesis_id": self.source_hypothesis_id,
            "target_hypothesis_id": self.target_hypothesis_id,
        }


class HypothesisGraph:
    """Branch-preserving hypothesis graph backed by immutable hive documents."""

    def __init__(self, store: LocalHiveStore | None = None) -> None:
        self.store = store
        self.nodes: dict[str, HypothesisNode] = {}
        self.edges: list[HypothesisEdge] = []
        if store is not None:
            for row in store.list_documents(schema=HYPOTHESIS_SCHEMA):
                content = row.get("content", {})
                if content.get("kind") == "node":
                    node = HypothesisNode(
                        hypothesis_id=content["hypothesis_id"],
                        candidate_id=content["candidate_id"],
                        branch_id=content["branch_id"],
                        parent_hypothesis_id=content.get("parent_hypothesis_id"),
                        domain=content["domain"],
                        status=content.get("status", "active"),
                        valid_until_ns=content.get("valid_until_ns"),
                    )
                    self.nodes[node.hypothesis_id] = node
                elif content.get("kind") == "edge":
                    self.edges.append(
                        HypothesisEdge(
                            source_hypothesis_id=content["source_hypothesis_id"],
                            target_hypothesis_id=content["target_hypothesis_id"],
                            relation=content["relation"],
                            condition=content.get("condition", {}),
                        )
                    )

    def register(
        self,
        *,
        candidate_id: str,
        branch_id: str,
        domain: str,
        parent_hypothesis_id: str | None = None,
        valid_until_ns: int | None = None,
    ) -> HypothesisNode:
        hypothesis_id = sha256_value(
            {
                "candidate_id": candidate_id,
                "branch_id": branch_id,
                "domain": domain,
                "parent_hypothesis_id": parent_hypothesis_id,
            }
        )
        node = HypothesisNode(
            hypothesis_id=hypothesis_id,
            candidate_id=candidate_id,
            branch_id=branch_id,
            parent_hypothesis_id=parent_hypothesis_id,
            domain=domain,
            valid_until_ns=valid_until_ns,
        )
        existing = self.nodes.get(hypothesis_id)
        if existing is not None and existing != node:
            raise CollectiveHiveError("hypothesis identity conflict")
        self.nodes[hypothesis_id] = node
        self._persist(HYPOTHESIS_SCHEMA, {"kind": "node", **node.as_dict()})
        return node

    def link(self, edge: HypothesisEdge) -> str:
        if edge.source_hypothesis_id not in self.nodes or edge.target_hypothesis_id not in self.nodes:
            raise CollectiveHiveError("hypothesis edge references an unknown node")
        if edge.source_hypothesis_id == edge.target_hypothesis_id:
            raise CollectiveHiveError("hypothesis cannot link to itself")
        if edge not in self.edges:
            self.edges.append(edge)
        self._persist(HYPOTHESIS_SCHEMA, {"kind": "edge", **edge.as_dict()})
        return sha256_value({"schema": HYPOTHESIS_SCHEMA, "kind": "edge", **edge.as_dict()})
    def resolve(self, hypothesis_id: str, status: str) -> HypothesisNode:
        node = self.nodes.get(hypothesis_id)
        if node is None:
            raise CollectiveHiveError("unknown hypothesis")
        if status not in {"active", "refuted", "superseded", "conditional", "expired"}:
            raise CollectiveHiveError("hypothesis status is unsupported")
        updated = replace(node, status=status)
        self.nodes[hypothesis_id] = updated
        self._persist(HYPOTHESIS_SCHEMA, {"kind": "node", **updated.as_dict()})
        return updated
        

    def active(self, *, domain: str | None = None) -> tuple[HypothesisNode, ...]:
        return tuple(
            node
            for node in self.nodes.values()
            if node.status == "active" and not node.expired and (domain is None or node.domain == domain)
        )

    def contradictions(self, hypothesis_id: str) -> tuple[HypothesisNode, ...]:
        target_ids = {
            edge.target_hypothesis_id
            for edge in self.edges
            if edge.source_hypothesis_id == hypothesis_id and edge.relation == "contradicts"
        }
        return tuple(self.nodes[item] for item in sorted(target_ids) if item in self.nodes)

    def _persist(self, schema: str, content: Mapping[str, Any]) -> None:
        if self.store is not None:
            self.store.put_document(make_document(schema, content))


@dataclass(frozen=True, slots=True)
class HiveQuery:
    query_id: str
    requester_instance_id: str
    kinds: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    required_branch: str | None = None
    minimum_reliability: float = 0.0
    maximum_work: int | None = None
    desired_roles: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.query_id, "query_id")
        _text(self.requester_instance_id, "requester_instance_id")
        object.__setattr__(self, "kinds", _tuple_text(self.kinds, "query kind"))
        object.__setattr__(self, "domains", _tuple_text(self.domains, "query domain"))
        object.__setattr__(self, "desired_roles", _tuple_text(self.desired_roles, "query role"))
        if self.required_branch is not None:
            _text(self.required_branch, "required_branch")
        _finite(self.minimum_reliability, "minimum_reliability")
        if self.maximum_work is not None and (isinstance(self.maximum_work, bool) or not isinstance(self.maximum_work, int) or self.maximum_work < 1):
            raise CollectiveHiveError("maximum_work must be positive")

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "domains": list(self.domains),
            "desired_roles": list(self.desired_roles),
            "kinds": list(self.kinds),
            "maximum_work": self.maximum_work,
            "minimum_reliability": self.minimum_reliability,
            "query_id": self.query_id,
            "requester_instance_id": self.requester_instance_id,
            "required_branch": self.required_branch,
        }


@dataclass(frozen=True, slots=True)
class HiveOffer:
    offer_id: str
    provider_instance_id: str
    candidate_id: str
    kind: str
    domain: str
    branch_id: str
    reliability: float
    work_units: int
    roles: tuple[str, ...] = ()
    diversity_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for label, value in (("offer_id", self.offer_id), ("provider_instance_id", self.provider_instance_id), ("candidate_id", self.candidate_id), ("kind", self.kind), ("domain", self.domain), ("branch_id", self.branch_id)):
            _text(value, label)
        _finite(self.reliability, "reliability")
        if isinstance(self.work_units, bool) or not isinstance(self.work_units, int) or self.work_units < 1:
            raise CollectiveHiveError("work_units must be positive")
        object.__setattr__(self, "roles", _tuple_text(self.roles, "offer role"))
        object.__setattr__(self, "diversity_keys", _tuple_text(self.diversity_keys, "diversity key"))

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "branch_id": self.branch_id,
            "candidate_id": self.candidate_id,
            "diversity_keys": list(self.diversity_keys),
            "domain": self.domain,
            "kind": self.kind,
            "offer_id": self.offer_id,
            "provider_instance_id": self.provider_instance_id,
            "reliability": self.reliability,
            "roles": list(self.roles),
            "work_units": self.work_units,
        }


@dataclass(frozen=True, slots=True)
class MethodPort:
    """One semantic method port and its concrete FieldProgram symbol."""

    name: str
    value_kind: str
    representation: str
    unit: str = "1"
    symbol: str | None = None

    def __post_init__(self) -> None:
        _text(self.name, "method port name")
        if self.value_kind not in {
            "boolean", "integer", "scalar", "text",
            "vector", "mapping", "sequence", "json",
        }:
            raise CollectiveHiveError("method port value_kind is unsupported")
        _text(self.representation, "method port representation")
        _text(self.unit, "method port unit")
        symbol = self.name if self.symbol is None else self.symbol
        object.__setattr__(self, "symbol", _text(symbol, "method port symbol"))

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "name": self.name,
            "representation": self.representation,
            "symbol": self.symbol,
            "unit": self.unit,
            "value_kind": self.value_kind,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MethodPort":
        return cls(**dict(value))


@dataclass(frozen=True, slots=True)
class MethodInterface:
    """Typed, unit-aware boundary around an executable contribution."""

    inputs: tuple[MethodPort, ...]
    outputs: tuple[MethodPort, ...]

    def __post_init__(self) -> None:
        for field_name in ("inputs", "outputs"):
            ports = tuple(
                item
                if isinstance(item, MethodPort)
                else MethodPort.from_dict(_mapping(item, f"method {field_name} port"))
                for item in getattr(self, field_name)
            )
            names = tuple(port.name for port in ports)
            symbols = tuple(port.symbol for port in ports)
            if len(names) != len(set(names)) or len(symbols) != len(set(symbols)):
                raise CollectiveHiveError(
                    f"method interface {field_name} names and symbols must be unique"
                )
            object.__setattr__(self, field_name, ports)
        if not self.outputs:
            raise CollectiveHiveError(
                "method interface requires at least one output"
            )

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "schema": METHOD_INTERFACE_SCHEMA,
            "inputs": [port.as_dict() for port in self.inputs],
            "outputs": [port.as_dict() for port in self.outputs],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MethodInterface":
        row = dict(value)
        if row.pop("schema", None) != METHOD_INTERFACE_SCHEMA:
            raise CollectiveHiveError("method interface schema is invalid")
        row["inputs"] = tuple(MethodPort.from_dict(item) for item in row["inputs"])
        row["outputs"] = tuple(MethodPort.from_dict(item) for item in row["outputs"])
        return cls(**row)


@dataclass(frozen=True, slots=True)
class ExecutableMethod:
    """Portable exact method plus the context needed to reuse it safely."""

    program: FieldProgram
    interface: MethodInterface
    assumptions: tuple[Mapping[str, Any], ...] = ()
    preconditions: tuple[Mapping[str, Any], ...] = ()
    effects: tuple[str, ...] = ()
    maximum_work: int = 256
    uncertainty: float = 0.0
    correction_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        program = self.program
        if not isinstance(program, FieldProgram):
            try:
                program = FieldProgram.from_dict(
                    _mapping(program, "executable method program")
                )
            except (FieldIntelligenceError, KeyError, TypeError, ValueError) as exc:
                raise CollectiveHiveError("executable method program is invalid") from exc
            object.__setattr__(self, "program", program)
        interface = self.interface
        if not isinstance(interface, MethodInterface):
            interface = MethodInterface.from_dict(
                _mapping(interface, "executable method interface")
            )
            object.__setattr__(self, "interface", interface)
        input_symbols = tuple(port.symbol for port in interface.inputs)
        output_symbols = tuple(port.symbol for port in interface.outputs)
        if set(input_symbols) != set(program.roles):
            raise CollectiveHiveError(
                "method interface inputs do not cover program roles exactly"
            )
        if set(output_symbols) != set(program.outputs):
            raise CollectiveHiveError(
                "method interface outputs do not cover program outputs exactly"
            )
        object.__setattr__(
            self,
            "assumptions",
            _tuple_mapping(self.assumptions, "method assumption"),
        )
        object.__setattr__(
            self,
            "preconditions",
            _tuple_mapping(self.preconditions, "method precondition"),
        )
        object.__setattr__(self, "effects", _tuple_text(self.effects, "method effect"))
        object.__setattr__(
            self,
            "correction_ids",
            _tuple_text(self.correction_ids, "method correction"),
        )
        if (
            isinstance(self.maximum_work, bool)
            or not isinstance(self.maximum_work, int)
            or self.maximum_work < len(program.steps)
        ):
            raise CollectiveHiveError(
                "method maximum_work must cover every program step"
            )
        _finite(self.uncertainty, "method uncertainty")

    @property
    def program_sha256(self) -> str:
        return sha256_value(self.program.as_dict())

    def execute(self, bindings: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(bindings, Mapping):
            raise CollectiveHiveError("method bindings must be a mapping")
        if set(bindings) != {port.name for port in self.interface.inputs}:
            raise CollectiveHiveError(
                "method bindings must cover interface inputs exactly"
            )
        program_bindings: dict[str, Any] = {}
        for port in self.interface.inputs:
            value = bindings[port.name]
            _validate_method_value(value, port.value_kind, f"method input {port.name}")
            program_bindings[str(port.symbol)] = value
        try:
            result = self.program.execute(
                program_bindings,
                max_steps=self.maximum_work,
            )
        except FieldIntelligenceError as exc:
            raise CollectiveHiveError("executable method rejected its inputs") from exc
        outputs: dict[str, Any] = {}
        for port in self.interface.outputs:
            value = result[str(port.symbol)]
            _validate_method_value(value, port.value_kind, f"method output {port.name}")
            outputs[port.name] = value
        return outputs

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "schema": EXECUTABLE_METHOD_SCHEMA,
            "assumptions": [dict(item) for item in self.assumptions],
            "correction_ids": list(self.correction_ids),
            "effects": list(self.effects),
            "interface": self.interface.as_dict(),
            "maximum_work": self.maximum_work,
            "preconditions": [dict(item) for item in self.preconditions],
            "program": self.program.as_dict(),
            "program_sha256": self.program_sha256,
            "uncertainty": self.uncertainty,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExecutableMethod":
        row = dict(value)
        if row.pop("schema", None) != EXECUTABLE_METHOD_SCHEMA:
            raise CollectiveHiveError("executable method schema is invalid")
        claimed_digest = row.pop("program_sha256", None)
        try:
            row["program"] = FieldProgram.from_dict(row["program"])
            row["interface"] = MethodInterface.from_dict(row["interface"])
            for name in (
                "assumptions",
                "preconditions",
                "effects",
                "correction_ids",
            ):
                row[name] = tuple(row.get(name, ()))
            method = cls(**row)
        except CollectiveHiveError:
            raise
        except (FieldIntelligenceError, KeyError, TypeError, ValueError) as exc:
            raise CollectiveHiveError(
                "executable method payload is invalid"
            ) from exc
        if claimed_digest != method.program_sha256:
            raise CollectiveHiveError(
                "executable method program digest does not match"
            )
        return method


@dataclass(frozen=True, slots=True)
class MethodConnection:
    source_component_id: str
    source_port: str
    target_component_id: str
    target_port: str

    def __post_init__(self) -> None:
        for label, value in (
            ("source_component_id", self.source_component_id),
            ("source_port", self.source_port),
            ("target_component_id", self.target_component_id),
            ("target_port", self.target_port),
        ):
            _text(value, f"method connection {label}")
        if self.source_component_id == self.target_component_id:
            raise CollectiveHiveError("a method connection cannot feed itself")

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "source_component_id": self.source_component_id,
            "source_port": self.source_port,
            "target_component_id": self.target_component_id,
            "target_port": self.target_port,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MethodConnection":
        return cls(**dict(value))


@dataclass(frozen=True, slots=True)
class MethodOutputBinding:
    output_port: str
    source_component_id: str
    source_port: str

    def __post_init__(self) -> None:
        _text(self.output_port, "method output binding output_port")
        _text(self.source_component_id, "method output binding source_component_id")
        _text(self.source_port, "method output binding source_port")

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "output_port": self.output_port,
            "source_component_id": self.source_component_id,
            "source_port": self.source_port,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MethodOutputBinding":
        return cls(**dict(value))


@dataclass(frozen=True, slots=True)
class MethodCompositionSpec:
    """A bounded dataflow graph over attributed collaboration artifacts."""

    program_id: str
    component_ids: tuple[str, ...]
    connections: tuple[MethodConnection, ...]
    outputs: tuple[MethodOutputBinding, ...]
    maximum_work: int
    maximum_prefix_code_bits: int = 4096

    def __post_init__(self) -> None:
        _text(self.program_id, "method composition program_id")
        object.__setattr__(
            self,
            "component_ids",
            _tuple_text(self.component_ids, "method composition component"),
        )
        if not self.component_ids:
            raise CollectiveHiveError("method composition requires a component")
        connections = tuple(
            item
            if isinstance(item, MethodConnection)
            else MethodConnection.from_dict(
                _mapping(item, "method composition connection")
            )
            for item in self.connections
        )
        outputs = tuple(
            item
            if isinstance(item, MethodOutputBinding)
            else MethodOutputBinding.from_dict(
                _mapping(item, "method composition output")
            )
            for item in self.outputs
        )
        targets = tuple(
            (item.target_component_id, item.target_port)
            for item in connections
        )
        output_names = tuple(item.output_port for item in outputs)
        if len(targets) != len(set(targets)):
            raise CollectiveHiveError(
                "method composition binds an input more than once"
            )
        if len(output_names) != len(set(output_names)):
            raise CollectiveHiveError(
                "method composition binds an output more than once"
            )
        object.__setattr__(self, "connections", connections)
        object.__setattr__(self, "outputs", outputs)
        if (
            isinstance(self.maximum_work, bool)
            or not isinstance(self.maximum_work, int)
            or self.maximum_work < 1
            or isinstance(self.maximum_prefix_code_bits, bool)
            or not isinstance(self.maximum_prefix_code_bits, int)
            or self.maximum_prefix_code_bits < 1
        ):
            raise CollectiveHiveError("method composition bounds must be positive")

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "schema": METHOD_COMPOSITION_SCHEMA,
            "component_ids": list(self.component_ids),
            "connections": [item.as_dict() for item in self.connections],
            "maximum_prefix_code_bits": self.maximum_prefix_code_bits,
            "maximum_work": self.maximum_work,
            "outputs": [item.as_dict() for item in self.outputs],
            "program_id": self.program_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MethodCompositionSpec":
        row = dict(value)
        if row.pop("schema", None) != METHOD_COMPOSITION_SCHEMA:
            raise CollectiveHiveError("method composition schema is invalid")
        row["component_ids"] = tuple(row["component_ids"])
        row["connections"] = tuple(
            MethodConnection.from_dict(item) for item in row["connections"]
        )
        row["outputs"] = tuple(
            MethodOutputBinding.from_dict(item) for item in row["outputs"]
        )
        return cls(**row)


@dataclass(frozen=True, slots=True)
class MethodCompositionResult:
    method: ExecutableMethod | None
    gaps: tuple[Mapping[str, Any], ...]
    provenance: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "gaps", _tuple_mapping(self.gaps, "composition gap"))
        object.__setattr__(
            self,
            "provenance",
            _tuple_mapping(self.provenance, "composition provenance"),
        )

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "schema": METHOD_COMPOSITION_RESULT_SCHEMA,
            "gaps": [dict(item) for item in self.gaps],
            "method": None if self.method is None else self.method.as_dict(),
            "provenance": [dict(item) for item in self.provenance],
            "status": (
                "blocked" if self.gaps else "ready" if self.method is not None
                else "descriptive"
            ),
        }


@dataclass(frozen=True, slots=True)
class CollaborationRequest:
    request_id: str
    requester_instance_id: str
    objective: Mapping[str, Any]
    desired_roles: tuple[str, ...]
    source_representation: str
    target_representation: str
    maximum_members: int
    maximum_work: int
    input_artifact_ids: tuple[str, ...] = ()
    required_interface: MethodInterface | None = None

    def __post_init__(self) -> None:
        _text(self.request_id, "collaboration request_id")
        _text(self.requester_instance_id, "collaboration requester_instance_id")
        object.__setattr__(
            self,
            "objective",
            _mapping(self.objective, "collaboration objective"),
        )
        object.__setattr__(
            self,
            "desired_roles",
            _tuple_text(self.desired_roles, "collaboration role"),
        )
        _text(self.source_representation, "collaboration source_representation")
        _text(self.target_representation, "collaboration target_representation")
        object.__setattr__(
            self,
            "input_artifact_ids",
            _tuple_text(self.input_artifact_ids, "collaboration input artifact"),
        )
        if (
            isinstance(self.maximum_members, bool)
            or not isinstance(self.maximum_members, int)
            or not 1 <= self.maximum_members <= 64
            or isinstance(self.maximum_work, bool)
            or not isinstance(self.maximum_work, int)
            or self.maximum_work < 1
        ):
            raise CollectiveHiveError("collaboration bounds are invalid")
        interface = self.required_interface
        if interface is not None and not isinstance(interface, MethodInterface):
            interface = MethodInterface.from_dict(
                _mapping(interface, "collaboration required interface")
            )
            object.__setattr__(self, "required_interface", interface)
        if interface is not None:
            if any(
                port.representation != self.source_representation
                for port in interface.inputs
            ) or any(
                port.representation != self.target_representation
                for port in interface.outputs
            ):
                raise CollectiveHiveError(
                    "collaboration interface representations do not match request"
                )

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "desired_roles": list(self.desired_roles),
            "input_artifact_ids": list(self.input_artifact_ids),
            "maximum_members": self.maximum_members,
            "maximum_work": self.maximum_work,
            "objective": dict(self.objective),
            "request_id": self.request_id,
            "requester_instance_id": self.requester_instance_id,
            "required_interface": (
                None
                if self.required_interface is None
                else self.required_interface.as_dict()
            ),
            "source_representation": self.source_representation,
            "target_representation": self.target_representation,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CollaborationRequest":
        row = dict(value)
        row["desired_roles"] = tuple(row["desired_roles"])
        row["input_artifact_ids"] = tuple(row.get("input_artifact_ids", ()))
        if row.get("required_interface") is not None:
            row["required_interface"] = MethodInterface.from_dict(
                row["required_interface"]
            )
        return cls(**row)


@dataclass(frozen=True, slots=True)
class CollaborationAssignment:
    assignment_id: str
    request_id: str
    assignee_instance_id: str
    role: str
    task: Mapping[str, Any]
    resource_allocation_id: str
    input_artifact_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for label, value in (
            ("assignment_id", self.assignment_id),
            ("request_id", self.request_id),
            ("assignee_instance_id", self.assignee_instance_id),
            ("role", self.role),
            ("resource_allocation_id", self.resource_allocation_id),
        ):
            _text(value, f"collaboration {label}")
        object.__setattr__(self, "task", _mapping(self.task, "collaboration task"))
        object.__setattr__(
            self,
            "input_artifact_ids",
            _tuple_text(self.input_artifact_ids, "assignment input artifact"),
        )

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "assignment_id": self.assignment_id,
            "assignee_instance_id": self.assignee_instance_id,
            "input_artifact_ids": list(self.input_artifact_ids),
            "request_id": self.request_id,
            "resource_allocation_id": self.resource_allocation_id,
            "role": self.role,
            "task": dict(self.task),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CollaborationAssignment":
        row = dict(value)
        row["input_artifact_ids"] = tuple(row.get("input_artifact_ids", ()))
        return cls(**row)


@dataclass(frozen=True, slots=True)
class CollaborationResponse:
    response_id: str
    assignment_id: str
    responder_instance_id: str
    status: str
    representation: str
    content: Mapping[str, Any]
    artifact_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    method: ExecutableMethod | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("response_id", self.response_id),
            ("assignment_id", self.assignment_id),
            ("responder_instance_id", self.responder_instance_id),
            ("status", self.status),
            ("representation", self.representation),
        ):
            _text(value, f"collaboration {label}")
        if self.status not in {"completed", "partial", "blocked", "failed"}:
            raise CollectiveHiveError("collaboration response status is invalid")
        object.__setattr__(
            self,
            "content",
            _mapping(self.content, "collaboration response content"),
        )
        for name in ("artifact_ids", "evidence_ids", "limitations"):
            object.__setattr__(
                self,
                name,
                _tuple_text(
                    getattr(self, name),
                    f"collaboration response {name}",
                ),
            )
        method = self.method
        if method is not None and not isinstance(method, ExecutableMethod):
            method = ExecutableMethod.from_dict(
                _mapping(method, "collaboration executable method")
            )
            object.__setattr__(self, "method", method)
        if method is not None:
            if self.status not in {"completed", "partial"}:
                raise CollectiveHiveError(
                    "blocked or failed response cannot carry an executable method"
                )
            if any(
                port.representation != self.representation
                for port in method.interface.outputs
            ):
                raise CollectiveHiveError(
                    "response representation does not match its method outputs"
                )

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "artifact_ids": list(self.artifact_ids),
            "assignment_id": self.assignment_id,
            "content": dict(self.content),
            "evidence_ids": list(self.evidence_ids),
            "limitations": list(self.limitations),
            "method": None if self.method is None else self.method.as_dict(),
            "representation": self.representation,
            "responder_instance_id": self.responder_instance_id,
            "response_id": self.response_id,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CollaborationResponse":
        row = dict(value)
        for name in ("artifact_ids", "evidence_ids", "limitations"):
            row[name] = tuple(row.get(name, ()))
        if row.get("method") is not None:
            row["method"] = ExecutableMethod.from_dict(row["method"])
        return cls(**row)


@dataclass(frozen=True, slots=True)
class RepresentationTranslation:
    translation_id: str
    source_response_id: str
    translator_instance_id: str
    source_representation: str
    target_representation: str
    translated_content: Mapping[str, Any]
    mapping: Mapping[str, Any]
    validation_status: str
    limitations: tuple[str, ...] = ()
    method: ExecutableMethod | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("translation_id", self.translation_id),
            ("source_response_id", self.source_response_id),
            ("translator_instance_id", self.translator_instance_id),
            ("source_representation", self.source_representation),
            ("target_representation", self.target_representation),
            ("validation_status", self.validation_status),
        ):
            _text(value, f"translation {label}")
        if self.validation_status not in {"validated", "lossy", "unvalidated"}:
            raise CollectiveHiveError("translation validation status is invalid")
        object.__setattr__(
            self,
            "translated_content",
            _mapping(self.translated_content, "translated content"),
        )
        object.__setattr__(
            self,
            "mapping",
            _mapping(self.mapping, "translation mapping"),
        )
        object.__setattr__(
            self,
            "limitations",
            _tuple_text(self.limitations, "translation limitation"),
        )
        method = self.method
        if method is not None and not isinstance(method, ExecutableMethod):
            method = ExecutableMethod.from_dict(
                _mapping(method, "translation executable method")
            )
            object.__setattr__(self, "method", method)
        if method is not None and (
            any(
                port.representation != self.source_representation
                for port in method.interface.inputs
            )
            or any(
                port.representation != self.target_representation
                for port in method.interface.outputs
            )
        ):
            raise CollectiveHiveError(
                "translation method representations do not match its declaration"
            )

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "limitations": list(self.limitations),
            "mapping": dict(self.mapping),
            "method": None if self.method is None else self.method.as_dict(),
            "source_representation": self.source_representation,
            "source_response_id": self.source_response_id,
            "target_representation": self.target_representation,
            "translated_content": dict(self.translated_content),
            "translation_id": self.translation_id,
            "translator_instance_id": self.translator_instance_id,
            "validation_status": self.validation_status,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RepresentationTranslation":
        row = dict(value)
        row["limitations"] = tuple(row.get("limitations", ()))
        if row.get("method") is not None:
            row["method"] = ExecutableMethod.from_dict(row["method"])
        return cls(**row)


@dataclass(frozen=True, slots=True)
class CollectiveSynthesis:
    synthesis_id: str
    request_id: str
    synthesizer_instance_id: str
    response_ids: tuple[str, ...]
    translation_ids: tuple[str, ...]
    result: Mapping[str, Any]
    agreements: tuple[str, ...] = ()
    disagreements: tuple[str, ...] = ()
    unresolved: tuple[str, ...] = ()
    composition: MethodCompositionSpec | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("synthesis_id", self.synthesis_id),
            ("request_id", self.request_id),
            ("synthesizer_instance_id", self.synthesizer_instance_id),
        ):
            _text(value, f"synthesis {label}")
        for name in (
            "response_ids",
            "translation_ids",
            "agreements",
            "disagreements",
            "unresolved",
        ):
            object.__setattr__(
                self,
                name,
                _tuple_text(getattr(self, name), f"synthesis {name}"),
            )
        if not self.response_ids:
            raise CollectiveHiveError("synthesis requires at least one response")
        object.__setattr__(
            self,
            "result",
            _mapping(self.result, "synthesis result"),
        )
        composition = self.composition
        if composition is not None and not isinstance(
            composition, MethodCompositionSpec
        ):
            composition = MethodCompositionSpec.from_dict(
                _mapping(composition, "synthesis composition")
            )
            object.__setattr__(self, "composition", composition)

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "agreements": list(self.agreements),
            "composition": (
                None if self.composition is None else self.composition.as_dict()
            ),
            "disagreements": list(self.disagreements),
            "request_id": self.request_id,
            "response_ids": list(self.response_ids),
            "result": dict(self.result),
            "synthesis_id": self.synthesis_id,
            "synthesizer_instance_id": self.synthesizer_instance_id,
            "translation_ids": list(self.translation_ids),
            "unresolved": list(self.unresolved),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CollectiveSynthesis":
        row = dict(value)
        for name in (
            "response_ids",
            "translation_ids",
            "agreements",
            "disagreements",
            "unresolved",
        ):
            row[name] = tuple(row.get(name, ()))
        if row.get("composition") is not None:
            row["composition"] = MethodCompositionSpec.from_dict(
                row["composition"]
            )
        return cls(**row)


_REQUEST_COMPONENT_ID = "$request"


def _method_port(
    ports: Sequence[MethodPort],
    name: str,
    label: str,
) -> MethodPort:
    matches = [port for port in ports if port.name == name]
    if len(matches) != 1:
        raise CollectiveHiveError(f"{label} references an unavailable method port")
    return matches[0]


def _require_compatible_ports(
    source: MethodPort,
    target: MethodPort,
    label: str,
) -> None:
    if (
        source.value_kind != target.value_kind
        or source.representation != target.representation
        or source.unit != target.unit
    ):
        raise CollectiveHiveError(
            f"{label} has incompatible type, representation, or unit"
        )


def _unique_mappings(
    values: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    seen: set[bytes] = set()
    result: list[Mapping[str, Any]] = []
    for value in values:
        key = canonical_json_bytes(value)
        if key not in seen:
            seen.add(key)
            result.append(_mapping(value, "method metadata"))
    return tuple(result)


def _composition_symbol(
    program_id: str,
    role: str,
    *parts: str,
) -> str:
    suffix = sha256_value(
        {
            "program_id": program_id,
            "role": role,
            "parts": list(parts),
        }
    )[:24]
    return f"@{role}:{suffix}"


def compile_collaborative_method(
    request: CollaborationRequest,
    responses: Sequence[CollaborationResponse],
    translations: Sequence[RepresentationTranslation],
    synthesis: CollectiveSynthesis,
) -> MethodCompositionResult:
    """Compile attributed partial methods into one checked FieldProgram graph."""

    if synthesis.request_id != request.request_id:
        raise CollectiveHiveError("synthesis and request identities do not match")
    spec = synthesis.composition
    if spec is None:
        return MethodCompositionResult(None, (), ())
    if request.required_interface is None:
        raise CollectiveHiveError(
            "executable synthesis requires a collaboration interface"
        )
    if spec.maximum_work > request.maximum_work:
        raise CollectiveHiveError(
            "method composition exceeds the collaboration work bound"
        )

    response_by_id = {item.response_id: item for item in responses}
    translation_by_id = {item.translation_id: item for item in translations}
    if len(response_by_id) != len(responses) or len(translation_by_id) != len(
        translations
    ):
        raise CollectiveHiveError("collaboration artifact identities are not unique")
    if set(response_by_id).intersection(translation_by_id):
        raise CollectiveHiveError(
            "response and translation identities must be distinct"
        )
    allowed_ids = set(synthesis.response_ids) | set(synthesis.translation_ids)
    methods: dict[str, ExecutableMethod] = {}
    provenance: list[Mapping[str, Any]] = []
    gaps: list[Mapping[str, Any]] = []
    for component_id in spec.component_ids:
        if component_id not in allowed_ids:
            raise CollectiveHiveError(
                "method composition uses an artifact outside the synthesis"
            )
        artifact_kind: str
        origin_instance_id: str
        method: ExecutableMethod | None
        provenance_details: dict[str, Any]
        if component_id in response_by_id:
            response = response_by_id[component_id]
            artifact_kind = "response"
            origin_instance_id = response.responder_instance_id
            method = response.method
            provenance_details = {
                "artifact_ids": list(response.artifact_ids),
                "evidence_ids": list(response.evidence_ids),
                "limitations": list(response.limitations),
            }
        elif component_id in translation_by_id:
            translation = translation_by_id[component_id]
            artifact_kind = "translation"
            origin_instance_id = translation.translator_instance_id
            method = translation.method
            provenance_details = {
                "limitations": list(translation.limitations),
                "source_response_id": translation.source_response_id,
            }
        else:
            raise CollectiveHiveError(
                "method composition references an unavailable artifact"
            )
        if method is None:
            gaps.append(
                {
                    "component_id": component_id,
                    "kind": "non-executable-component",
                    "required": "executable-method",
                }
            )
            provenance.append(
                {
                    "artifact_id": component_id,
                    "artifact_kind": artifact_kind,
                    "executable": False,
                    "origin_instance_id": origin_instance_id,
                    **provenance_details,
                }
            )
            continue
        methods[component_id] = method
        provenance.append(
            {
                "artifact_id": component_id,
                "artifact_kind": artifact_kind,
                "correction_ids": list(method.correction_ids),
                "executable": True,
                "interface_sha256": sha256_value(method.interface.as_dict()),
                "origin_instance_id": origin_instance_id,
                "program_id": method.program.program_id,
                "program_sha256": method.program_sha256,
                "program_version": method.program.version,
                **provenance_details,
            }
        )
    if gaps:
        return MethodCompositionResult(
            None,
            tuple(gaps),
            tuple(provenance),
        )

    required = request.required_interface
    connection_by_target = {
        (item.target_component_id, item.target_port): item
        for item in spec.connections
    }
    dependencies: dict[str, set[str]] = {
        component_id: set() for component_id in spec.component_ids
    }

    def source_port(component_id: str, port_name: str) -> MethodPort:
        if component_id == _REQUEST_COMPONENT_ID:
            return _method_port(
                required.inputs,
                port_name,
                "composition request input",
            )
        if component_id not in methods:
            raise CollectiveHiveError(
                "method connection source is not a selected component"
            )
        return _method_port(
            methods[component_id].interface.outputs,
            port_name,
            "method connection source",
        )

    for connection in spec.connections:
        if connection.target_component_id not in methods:
            raise CollectiveHiveError(
                "method connection target is not a selected component"
            )
        target = _method_port(
            methods[connection.target_component_id].interface.inputs,
            connection.target_port,
            "method connection target",
        )
        source = source_port(
            connection.source_component_id,
            connection.source_port,
        )
        _require_compatible_ports(source, target, "method connection")
        if connection.source_component_id != _REQUEST_COMPONENT_ID:
            dependencies[connection.target_component_id].add(
                connection.source_component_id
            )
    for component_id, method in methods.items():
        for port in method.interface.inputs:
            if (component_id, port.name) not in connection_by_target:
                gaps.append(
                    {
                        "component_id": component_id,
                        "expected": port.as_dict(),
                        "kind": "missing-input-binding",
                        "port": port.name,
                    }
                )

    output_by_name = {item.output_port: item for item in spec.outputs}
    required_output_names = {port.name for port in required.outputs}
    unknown_outputs = set(output_by_name) - required_output_names
    if unknown_outputs:
        raise CollectiveHiveError(
            "method composition binds an undeclared synthesis output"
        )
    for port in required.outputs:
        binding = output_by_name.get(port.name)
        if binding is None:
            gaps.append(
                {
                    "expected": port.as_dict(),
                    "kind": "missing-output-binding",
                    "port": port.name,
                }
            )
            continue
        source = source_port(binding.source_component_id, binding.source_port)
        _require_compatible_ports(source, port, "method output binding")
    if gaps:
        return MethodCompositionResult(
            None,
            tuple(gaps),
            tuple(provenance),
        )

    order_index = {
        component_id: index
        for index, component_id in enumerate(spec.component_ids)
    }
    ready = sorted(
        (
            component_id
            for component_id, upstream in dependencies.items()
            if not upstream
        ),
        key=order_index.__getitem__,
    )
    order: list[str] = []
    pending = {key: set(value) for key, value in dependencies.items()}
    while ready:
        component_id = ready.pop(0)
        order.append(component_id)
        for candidate in spec.component_ids:
            if component_id not in pending[candidate]:
                continue
            pending[candidate].remove(component_id)
            if not pending[candidate] and candidate not in order and candidate not in ready:
                ready.append(candidate)
                ready.sort(key=order_index.__getitem__)
    if len(order) != len(spec.component_ids):
        raise CollectiveHiveError("method composition graph contains a cycle")

    declared_work = sum(method.maximum_work for method in methods.values())
    declared_work += len(required.outputs)
    if declared_work > spec.maximum_work:
        raise CollectiveHiveError(
            "component work bounds exceed the composition work bound"
        )
    prefix_bits = sum(
        method.program.prefix_code_bits for method in methods.values()
    )
    if prefix_bits > spec.maximum_prefix_code_bits:
        raise CollectiveHiveError(
            "component descriptions exceed the composition prefix-code bound"
        )

    external_symbols = {
        port.name: _composition_symbol(spec.program_id, "input", port.name)
        for port in required.inputs
    }
    roles = tuple(external_symbols[port.name] for port in required.inputs)
    steps: list[PrimitiveStep] = []
    output_symbols: dict[tuple[str, str], str] = {}
    guards: list[Guard] = []
    support_event_ids: list[str] = []
    program_dependencies: list[str] = []
    known_exceptions: list[str] = []

    def source_symbol(component_id: str, port_name: str) -> str:
        if component_id == _REQUEST_COMPONENT_ID:
            return external_symbols[port_name]
        return output_symbols[(component_id, port_name)]

    for component_id in order:
        method = methods[component_id]
        local_symbols: dict[str, str] = {}
        for port in method.interface.inputs:
            connection = connection_by_target[(component_id, port.name)]
            local_symbols[str(port.symbol)] = source_symbol(
                connection.source_component_id,
                connection.source_port,
            )
        for index, step in enumerate(method.program.steps):
            output = _composition_symbol(
                spec.program_id,
                "step",
                component_id,
                str(index),
                step.output,
            )
            steps.append(
                PrimitiveStep(
                    operation=step.operation,
                    output=output,
                    inputs=tuple(local_symbols[name] for name in step.inputs),
                    literal=step.literal,
                )
            )
            local_symbols[step.output] = output
        for port in method.interface.outputs:
            output_symbols[(component_id, port.name)] = local_symbols[
                str(port.symbol)
            ]
        guards.extend(method.program.guards)
        support_event_ids.extend(method.program.support_event_ids)
        program_dependencies.extend(
            (
                f"hive-{provenance[order_index[component_id]]['artifact_kind']}:{component_id}",
                method.program.program_id,
                *method.program.dependencies,
            )
        )
        known_exceptions.extend(method.program.known_exceptions)

    composed_output_ports: list[MethodPort] = []
    program_outputs: list[str] = []
    for port in required.outputs:
        binding = output_by_name[port.name]
        alias = _composition_symbol(spec.program_id, "output", port.name)
        steps.append(
            PrimitiveStep(
                operation="identity",
                output=alias,
                inputs=(
                    source_symbol(
                        binding.source_component_id,
                        binding.source_port,
                    ),
                ),
            )
        )
        program_outputs.append(alias)
        composed_output_ports.append(replace(port, symbol=alias))
    if len(steps) > spec.maximum_work:
        raise CollectiveHiveError(
            "compiled method exceeds the composition work bound"
        )

    unique_guards: dict[bytes, Guard] = {}
    for guard in guards:
        unique_guards[canonical_json_bytes(guard.as_dict())] = guard
    try:
        program = FieldProgram(
            program_id=spec.program_id,
            version=1,
            roles=roles,
            steps=tuple(steps),
            outputs=tuple(program_outputs),
            guards=tuple(unique_guards.values()),
            support_event_ids=tuple(dict.fromkeys(support_event_ids)),
            dependencies=tuple(dict.fromkeys(program_dependencies)),
            known_exceptions=tuple(dict.fromkeys(known_exceptions)),
            prefix_code_bits=prefix_bits,
            status="candidate",
        )
    except FieldIntelligenceError as exc:
        raise CollectiveHiveError("compiled collaboration program is invalid") from exc
    interface = MethodInterface(
        inputs=tuple(
            replace(port, symbol=external_symbols[port.name])
            for port in required.inputs
        ),
        outputs=tuple(composed_output_ports),
    )
    assumptions = _unique_mappings(
        tuple(
            assumption
            for component_id in order
            for assumption in methods[component_id].assumptions
        )
    )
    preconditions = _unique_mappings(
        tuple(
            precondition
            for component_id in order
            for precondition in methods[component_id].preconditions
        )
    )
    effects = tuple(
        dict.fromkeys(
            effect
            for component_id in order
            for effect in methods[component_id].effects
        )
    )
    correction_ids = tuple(
        dict.fromkeys(
            correction_id
            for component_id in order
            for correction_id in methods[component_id].correction_ids
        )
    )
    method = ExecutableMethod(
        program=program,
        interface=interface,
        assumptions=assumptions,
        preconditions=preconditions,
        effects=effects,
        maximum_work=declared_work,
        uncertainty=max(
            (methods[component_id].uncertainty for component_id in order),
            default=0.0,
        ),
        correction_ids=correction_ids,
    )
    return MethodCompositionResult(
        method,
        (),
        tuple(provenance),
    )


@dataclass(frozen=True, slots=True)
class AffectReport:
    """Attributed cooperative-affect message; never a donor-state transfer."""

    message_id: str
    sender_instance_id: str
    recipient_scope: str
    report_kind: str
    interpretation_status: str
    requested_help: Mapping[str, Any]
    content: Mapping[str, Any]
    applicability: Mapping[str, Any]
    question_ref: Mapping[str, Any] | None = None
    goal_ref: Mapping[str, Any] | None = None
    episode_id: str | None = None
    evidence_roots: tuple[Mapping[str, Any], ...] = ()
    visibility_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for label, value in (
            ("message_id", self.message_id),
            ("sender_instance_id", self.sender_instance_id),
            ("recipient_scope", self.recipient_scope),
            ("report_kind", self.report_kind),
            ("interpretation_status", self.interpretation_status),
        ):
            _text(value, f"affect report {label}")
        if self.report_kind not in {
            "concern", "opportunity", "help-request", "regulation-lesson",
        }:
            raise CollectiveHiveError("affect report kind is invalid")
        if self.interpretation_status not in {
            "interpreted", "tentative", "restricted", "unknown",
        }:
            raise CollectiveHiveError("affect report interpretation status is invalid")
        for name in ("requested_help", "content", "applicability"):
            object.__setattr__(
                self, name, _mapping(getattr(self, name), f"affect report {name}"),
            )
        for name in ("question_ref", "goal_ref"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self, name, _mapping(value, f"affect report {name}"),
                )
        if self.episode_id is not None:
            _text(self.episode_id, "affect report episode_id")
        normalized_roots = tuple(
            _mapping(root, "affect report evidence root")
            for root in self.evidence_roots
        )
        if len({canonical_json_bytes(root) for root in normalized_roots}) != len(
            normalized_roots
        ):
            raise CollectiveHiveError("affect report evidence roots must be unique")
        object.__setattr__(self, "evidence_roots", normalized_roots)
        object.__setattr__(
            self, "visibility_refs",
            _tuple_text(self.visibility_refs, "affect report visibility reference"),
        )

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "applicability": dict(self.applicability),
            "content": dict(self.content),
            "episode_id": self.episode_id,
            "evidence_roots": [dict(root) for root in self.evidence_roots],
            "goal_ref": None if self.goal_ref is None else dict(self.goal_ref),
            "interpretation_status": self.interpretation_status,
            "message_id": self.message_id,
            "question_ref": (
                None if self.question_ref is None else dict(self.question_ref)
            ),
            "recipient_scope": self.recipient_scope,
            "report_kind": self.report_kind,
            "requested_help": dict(self.requested_help),
            "sender_instance_id": self.sender_instance_id,
            "visibility_refs": list(self.visibility_refs),
        }


class QueryRouter:
    """Demand-driven query and offer matcher."""

    def __init__(self, store: LocalHiveStore | None = None) -> None:
        self.store = store
        self.offers: dict[str, HiveOffer] = {}
        if store is not None:
            for row in store.list_documents(schema=OFFER_SCHEMA):
                content = row.get("content", {})
                offer = HiveOffer(
                    offer_id=content["offer_id"],
                    provider_instance_id=content["provider_instance_id"],
                    candidate_id=content["candidate_id"],
                    kind=content["kind"],
                    domain=content["domain"],
                    branch_id=content["branch_id"],
                    reliability=content["reliability"],
                    work_units=content["work_units"],
                    roles=tuple(content.get("roles", ())),
                    diversity_keys=tuple(content.get("diversity_keys", ())),
                )
                self.offers[offer.offer_id] = offer

    def publish(self, offer: HiveOffer) -> str:
        self.offers[offer.offer_id] = offer
        if self.store is not None:
            self.store.put_document(make_document(OFFER_SCHEMA, offer.as_dict()))
        return offer.offer_id

    def request(self, query: HiveQuery) -> str:
        if self.store is not None:
            self.store.put_document(make_document(QUERY_SCHEMA, query.as_dict()))
        return query.query_id

    def match(self, query: HiveQuery, *, limit: int = 16) -> tuple[HiveOffer, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise CollectiveHiveError("limit must be positive")
        candidates = []
        for offer in self.offers.values():
            if query.kinds and offer.kind not in query.kinds:
                continue
            if query.domains and offer.domain not in query.domains:
                continue
            if query.required_branch is not None and offer.branch_id != query.required_branch:
                continue
            if offer.reliability < query.minimum_reliability:
                continue
            if query.maximum_work is not None and offer.work_units > query.maximum_work:
                continue
            if query.desired_roles and not set(query.desired_roles).intersection(offer.roles):
                continue
            score = offer.reliability - 0.001 * offer.work_units
            candidates.append((score, offer.offer_id, offer))
        candidates.sort(key=lambda row: (-row[0], row[1]))
        return tuple(row[2] for row in candidates[:limit])


@dataclass(frozen=True, slots=True)
class DiversityProfile:
    instance_id: str
    field_profile_sha256: str
    domain: str
    branch_id: str
    seed: int | None = None

    def keys(self) -> tuple[str, ...]:
        return tuple(
            value
            for value in (
                self.instance_id,
                self.field_profile_sha256,
                self.domain,
                self.branch_id,
                None if self.seed is None else str(self.seed),
            )
            if value is not None
        )


class DiversitySelector:
    """Greedy coverage selector that keeps minority field regimes alive."""

    @staticmethod
    def select(
        items: Sequence[Any],
        profiles: Mapping[str, DiversityProfile],
        *,
        limit: int,
    ) -> tuple[Any, ...]:
        if limit < 1:
            raise CollectiveHiveError("diversity limit must be positive")
        remaining = list(items)
        selected: list[Any] = []
        covered: set[str] = set()
        while remaining and len(selected) < limit:
            scored: list[tuple[int, str, Any]] = []
            for item in remaining:
                item_id = (
                    item
                    if isinstance(item, str) and item in profiles
                    else getattr(item, "object_id", getattr(item, "candidate_id", str(id(item))))
                )
                profile = profiles.get(item_id)
                keys = set(profile.keys()) if profile is not None else set()
                novelty = len(keys - covered)
                scored.append((novelty, str(item_id), item))
            scored.sort(key=lambda row: (-row[0], row[1]))
            _, item_id, chosen = scored[0]
            selected.append(chosen)
            remaining.remove(chosen)
            profile = profiles.get(item_id)
            if profile is not None:
                covered.update(profile.keys())
        return tuple(selected)


@dataclass(frozen=True, slots=True)
class RoleAssignment:
    instance_id: str
    role: str
    capabilities: tuple[str, ...]
    load: float = 0.0
    active: bool = True

    def __post_init__(self) -> None:
        _text(self.instance_id, "instance_id")
        _text(self.role, "role")
        object.__setattr__(self, "capabilities", _tuple_text(self.capabilities, "capability"))
        _finite(self.load, "load")

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "active": self.active,
            "capabilities": list(self.capabilities),
            "instance_id": self.instance_id,
            "load": self.load,
            "role": self.role,
        }


SPECIALIST_ROLES = frozenset({"scout", "critic", "replicator", "translator", "synthesizer", "cartographer", "operator", "historian"})


class RoleRouter:
    def __init__(self, store: LocalHiveStore | None = None) -> None:
        self.store = store
        self.assignments: dict[str, RoleAssignment] = {}
        if store is not None:
            for row in store.list_documents(schema=ROLE_SCHEMA):
                content = row.get("content", {})
                assignment = RoleAssignment(
                    instance_id=content["instance_id"],
                    role=content["role"],
                    capabilities=tuple(content.get("capabilities", ())),
                    load=content.get("load", 0.0),
                    active=content.get("active", True),
                )
                self.assignments[assignment.instance_id] = assignment

    def assign(self, assignment: RoleAssignment) -> str:
        if assignment.role not in SPECIALIST_ROLES:
            raise CollectiveHiveError("unsupported specialist role")
        self.assignments[assignment.instance_id] = assignment
        if self.store is not None:
            self.store.put_document(make_document(ROLE_SCHEMA, assignment.as_dict()))
        return sha256_value(assignment.as_dict())

    def choose(self, role: str, required_capabilities: Sequence[str] = ()) -> RoleAssignment:
        _text(role, "role")
        required = set(_tuple_text(required_capabilities, "required capability"))
        candidates = [
            assignment
            for assignment in self.assignments.values()
            if assignment.active and assignment.role == role and required.issubset(assignment.capabilities)
        ]
        if not candidates:
            raise CollectiveHiveError("no specialist is available for requested role")
        return min(candidates, key=lambda assignment: (assignment.load, assignment.instance_id))


@dataclass(frozen=True, slots=True)
class AdaptationFork:
    fork_id: str
    parent_bundle_id: str
    instance_id: str
    parent_profile_sha256: str
    local_profile_sha256: str
    changes: Mapping[str, Any]
    status: str = "proposed"
    created_ns: int = 0

    def __post_init__(self) -> None:
        _text(self.fork_id, "fork_id")
        _digest(self.parent_bundle_id, "parent_bundle_id")
        _text(self.instance_id, "instance_id")
        _digest(self.parent_profile_sha256, "parent_profile_sha256")
        _digest(self.local_profile_sha256, "local_profile_sha256")
        object.__setattr__(self, "changes", _mapping(self.changes, "fork changes"))
        if self.status not in {"proposed", "accepted", "refuted", "superseded"}:
            raise CollectiveHiveError("fork status is unsupported")

    @property
    def object_id(self) -> str:
        return sha256_value({"schema": FORK_SCHEMA, "content": self.as_dict()})

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "changes": dict(self.changes),
            "created_ns": self.created_ns,
            "fork_id": self.fork_id,
            "instance_id": self.instance_id,
            "local_profile_sha256": self.local_profile_sha256,
            "parent_bundle_id": self.parent_bundle_id,
            "parent_profile_sha256": self.parent_profile_sha256,
            "status": self.status,
        }


class AdaptationManager:
    def __init__(self, store: LocalHiveStore | None = None) -> None:
        self.store = store

    def propose(
        self,
        *,
        parent_bundle_id: str,
        instance_id: str,
        parent_profile_sha256: str,
        local_profile_sha256: str,
        changes: Mapping[str, Any],
    ) -> AdaptationFork:
        fork_id = sha256_value(
            {
                "changes": changes,
                "instance_id": instance_id,
                "local_profile_sha256": local_profile_sha256,
                "parent_bundle_id": parent_bundle_id,
            }
        )
        fork = AdaptationFork(
            fork_id=fork_id,
            parent_bundle_id=parent_bundle_id,
            instance_id=instance_id,
            parent_profile_sha256=parent_profile_sha256,
            local_profile_sha256=local_profile_sha256,
            changes=changes,
            created_ns=time.time_ns(),
        )
        if self.store is not None:
            self.store.put_document(make_document(FORK_SCHEMA, fork.as_dict()))
        return fork


@dataclass(frozen=True, slots=True)
class ConsolidatedMemory:
    memory_id: str
    candidate_id: str
    source_experience_ids: tuple[str, ...]
    source_count: int
    domain_coverage: tuple[str, ...]
    best_score: float
    status: str = "active"
    valid_until_ns: int | None = None

    def __post_init__(self) -> None:
        _text(self.memory_id, "memory_id")
        _text(self.candidate_id, "candidate_id")
        object.__setattr__(self, "source_experience_ids", _tuple_text(self.source_experience_ids, "source experience"))
        if self.source_count != len(self.source_experience_ids):
            raise CollectiveHiveError("source_count does not match source experiences")
        object.__setattr__(self, "domain_coverage", _tuple_text(self.domain_coverage, "domain coverage"))
        _finite(self.best_score, "best_score")
        if self.status not in {"active", "archived", "expired"}:
            raise CollectiveHiveError("memory status is unsupported")

    @property
    def expired(self) -> bool:
        return self.valid_until_ns is not None and time.time_ns() > self.valid_until_ns

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "best_score": self.best_score,
            "candidate_id": self.candidate_id,
            "domain_coverage": list(self.domain_coverage),
            "memory_id": self.memory_id,
            "source_count": self.source_count,
            "source_experience_ids": list(self.source_experience_ids),
            "status": "expired" if self.expired else self.status,
            "valid_until_ns": self.valid_until_ns,
        }


class MemoryConsolidator:
    def __init__(self, store: LocalHiveStore | None = None) -> None:
        self.store = store

    def consolidate(
        self,
        capsules: Sequence[ExperienceCapsule],
        *,
        valid_for_ns: int | None = None,
    ) -> tuple[ConsolidatedMemory, ...]:
        groups: dict[str, list[ExperienceCapsule]] = {}
        for capsule in capsules:
            key = sha256_value({"kind": capsule.candidate.kind, "object": capsule.candidate.object})
            groups.setdefault(key, []).append(capsule)
        memories: list[ConsolidatedMemory] = []
        for candidate_id, rows in sorted(groups.items()):
            domains = sorted({str(row.episode.context.get("domain", "unspecified")) for row in rows})
            memory = ConsolidatedMemory(
                memory_id=sha256_value({"schema": CONSOLIDATION_SCHEMA, "candidate_id": candidate_id, "sources": sorted(row.object_id for row in rows)}),
                candidate_id=candidate_id,
                source_experience_ids=tuple(sorted(row.object_id for row in rows)),
                source_count=len(rows),
                domain_coverage=tuple(domains),
                best_score=1.0 - min(row.episode.uncertainty for row in rows),
                valid_until_ns=None if valid_for_ns is None else time.time_ns() + valid_for_ns,
            )
            memories.append(memory)
            if self.store is not None:
                self.store.put_document(make_document(CONSOLIDATION_SCHEMA, memory.as_dict()))
        return tuple(memories)

    def expire(self, memories: Sequence[ConsolidatedMemory], *, now_ns: int | None = None) -> tuple[ConsolidatedMemory, ...]:
        now = time.time_ns() if now_ns is None else now_ns
        expired: list[ConsolidatedMemory] = []
        for memory in memories:
            if memory.valid_until_ns is not None and now > memory.valid_until_ns and memory.status == "active":
                updated = replace(memory, status="expired")
                expired.append(updated)
                if self.store is not None:
                    self.store.put_document(make_document(EXPIRATION_SCHEMA, {"memory_id": memory.memory_id, "expired_ns": now, "status": "expired"}))
        return tuple(expired)


class CollectiveHive:
    """Convenience façade exposing all collective improvements on one store."""

    def __init__(self, store: LocalHiveStore) -> None:
        if not isinstance(store, LocalHiveStore):
            raise CollectiveHiveError("collective hive requires LocalHiveStore")
        self.store = store
        self.graph = HypothesisGraph(store)
        self.router = QueryRouter(store)
        self.reputation = ReputationLedger(store)
        self.roles = RoleRouter(store)
        self.adaptations = AdaptationManager(store)
        self.memories = MemoryConsolidator(store)

    def record_identity(self, identity: InstanceIdentity) -> str:
        return self.store.put_document(identity.as_dict())

    def record_outcome(self, outcome: OutcomeEvidence) -> str:
        return self.store.put_document(outcome.document())
    def record_execution_assessment(
        self, assessment: ExecutionAssessment
    ) -> str:
        if not isinstance(assessment, ExecutionAssessment):
            raise CollectiveHiveError(
                "execution assessment must be ExecutionAssessment"
            )
        for trace_id in assessment.trace_document_ids:
            try:
                self.store.get_document(trace_id)
            except HiveStoreError as exc:
                raise CollectiveHiveError(
                    "execution assessment references unavailable trace evidence"
                ) from exc
        return self.store.put_document(assessment.document())

    def record_population_ledger(self, ledger: PopulationOutcomeLedger) -> str:
        if not isinstance(ledger, PopulationOutcomeLedger):
            raise CollectiveHiveError("population ledger must be PopulationOutcomeLedger")
        return self.store.put_document(ledger.document())

    def list_population_ledgers(self) -> tuple[Mapping[str, Any], ...]:
        return self.store.list_documents(schema=POPULATION_ROLLOUT_SCHEMA)
    def record_round_ledger(self, ledger: PopulationRoundLedger) -> str:
        if not isinstance(ledger, PopulationRoundLedger):
            raise CollectiveHiveError("round ledger must be PopulationRoundLedger")
        return self.store.put_document(ledger.document())

    def list_round_ledgers(self) -> tuple[Mapping[str, Any], ...]:
        return self.store.list_documents(schema=POPULATION_ROUNDS_SCHEMA)

    def verify_population_ledger(self, ledger: PopulationOutcomeLedger) -> bool:
        if not isinstance(ledger, PopulationOutcomeLedger):
            raise CollectiveHiveError("population ledger must be PopulationOutcomeLedger")
        try:
            if self.store.get_document(ledger.object_id) != ledger.document():
                return False
            for member in ledger.members:
                if member.outcome_id is None:
                    continue
                document = self.store.get_document(member.outcome_id)
                content = document.get("content", {})
                if (
                    document.get("schema") != OUTCOME_SCHEMA
                    or content.get("bundle_id") != ledger.bundle_id
                    or content.get("protocol_sha256") != ledger.protocol_sha256
                    or content.get("recipient_instance_id") != member.instance_id
                    or content.get("adoption_receipt_id") != member.adoption_receipt_id
                ):
                    return False
                assessment_id = content.get("execution_assessment_id")
                if not isinstance(assessment_id, str):
                    return False
                assessment_document = self.store.get_document(
                    assessment_id
                )
                assessment = ExecutionAssessment.from_document(
                    assessment_document
                )
                if (
                    assessment.bundle_id != ledger.bundle_id
                    or assessment.recipient_instance_id
                    != member.instance_id
                    or assessment.adoption_receipt_id
                    != member.adoption_receipt_id
                    or assessment.protocol_sha256
                    != ledger.protocol_sha256
                    or list(assessment.trace_document_ids)
                    != content.get("trace_document_ids")
                ):
                    return False
                for trace_id in assessment.trace_document_ids:
                    self.store.get_document(trace_id)
        except (CollectiveHiveError, HiveStoreError):
            return False
        return True

    def record_profile(self, profile: ReviewerProfile) -> str:
        return self.reputation.save(profile)

    def calibrate_reviewers(
        self,
        profiles: Mapping[str, ReviewerProfile],
        *,
        predicted_support: Mapping[str, float],
        actual_success: bool,
        independent_ids: Sequence[str] = (),
    ) -> Mapping[str, ReviewerProfile]:
        return self.reputation.calibrate_outcome(
            profiles,
            predicted_support=predicted_support,
            actual_success=actual_success,
            independent_ids=independent_ids,
        )
    def calibrate_population(
        self,
        ledger: PopulationOutcomeLedger,
        profiles: Mapping[str, ReviewerProfile],
        *,
        predicted_support: Mapping[str, float],
        independent_ids: Sequence[str] = (),
    ) -> Mapping[str, ReviewerProfile]:
        if not self.verify_population_ledger(ledger):
            raise CollectiveHiveError("population evidence is not verified")
        return self.calibrate_reviewers(
            profiles,
            predicted_support=predicted_support,
            actual_success=ledger.status == "accepted",
            independent_ids=independent_ids,
        )

    def weighted_quorum(
        self,
        reviews: Sequence[Review],
        profiles: Mapping[str, ReviewerProfile],
        identities: Mapping[str, InstanceIdentity],
        *,
        origin_instance_ids: Sequence[str] = (),
        minimum_support_weight: float = 1.0,
        minimum_independent_reviewers: int = 2,
    ) -> QuorumReport:
        return weighted_quorum(
            reviews,
            profiles,
            identities,
            origin_instance_ids=origin_instance_ids,
            minimum_support_weight=minimum_support_weight,
            minimum_independent_reviewers=minimum_independent_reviewers,
        )

    def record_query(self, query: HiveQuery) -> str:
        return self.router.request(query)

    def publish_offer(self, offer: HiveOffer) -> str:
        return self.router.publish(offer)
    def _require_collaboration_artifact(
        self, schema: str, key: str, value: str,
    ) -> Mapping[str, Any]:
        for document in self.store.list_documents(schema=schema):
            content = document.get("content", {})
            if isinstance(content, Mapping) and content.get(key) == value:
                return content
        raise CollectiveHiveError(f"referenced {schema} artifact is unavailable")

    def record_collaboration_request(self, request: CollaborationRequest) -> str:
        if not isinstance(request, CollaborationRequest):
            raise CollectiveHiveError("collaboration request has the wrong type")
        return self.store.put_document(
            make_document(COLLABORATION_REQUEST_SCHEMA, request.as_dict())
        )

    def record_collaboration_assignment(
        self, assignment: CollaborationAssignment,
    ) -> str:
        if not isinstance(assignment, CollaborationAssignment):
            raise CollectiveHiveError("collaboration assignment has the wrong type")
        request = self._require_collaboration_artifact(
            COLLABORATION_REQUEST_SCHEMA, "request_id", assignment.request_id,
        )
        if assignment.assignee_instance_id == request["requester_instance_id"]:
            raise CollectiveHiveError("a collaboration assignment must cross an owner boundary")
        return self.store.put_document(
            make_document(COLLABORATION_ASSIGNMENT_SCHEMA, assignment.as_dict())
        )

    def record_collaboration_response(
        self, response: CollaborationResponse,
    ) -> str:
        if not isinstance(response, CollaborationResponse):
            raise CollectiveHiveError("collaboration response has the wrong type")
        assignment = self._require_collaboration_artifact(
            COLLABORATION_ASSIGNMENT_SCHEMA,
            "assignment_id",
            response.assignment_id,
        )
        if assignment["assignee_instance_id"] != response.responder_instance_id:
            raise CollectiveHiveError("only the assigned owner may issue the response")
        request = CollaborationRequest.from_dict(
            self._require_collaboration_artifact(
                COLLABORATION_REQUEST_SCHEMA,
                "request_id",
                str(assignment["request_id"]),
            )
        )
        if (
            response.method is not None
            and response.method.maximum_work > request.maximum_work
        ):
            raise CollectiveHiveError(
                "response method exceeds the collaboration work bound"
            )
        return self.store.put_document(
            make_document(COLLABORATION_RESPONSE_SCHEMA, response.as_dict())
        )

    def record_representation_translation(
        self, translation: RepresentationTranslation,
    ) -> str:
        if not isinstance(translation, RepresentationTranslation):
            raise CollectiveHiveError("representation translation has the wrong type")
        response = CollaborationResponse.from_dict(
            self._require_collaboration_artifact(
                COLLABORATION_RESPONSE_SCHEMA,
                "response_id",
                translation.source_response_id,
            )
        )
        if response.representation != translation.source_representation:
            raise CollectiveHiveError(
                "translation source representation does not match"
            )
        assignment = CollaborationAssignment.from_dict(
            self._require_collaboration_artifact(
                COLLABORATION_ASSIGNMENT_SCHEMA,
                "assignment_id",
                response.assignment_id,
            )
        )
        request = CollaborationRequest.from_dict(
            self._require_collaboration_artifact(
                COLLABORATION_REQUEST_SCHEMA,
                "request_id",
                assignment.request_id,
            )
        )
        if (
            translation.method is not None
            and translation.method.maximum_work > request.maximum_work
        ):
            raise CollectiveHiveError(
                "translation method exceeds the collaboration work bound"
            )
        return self.store.put_document(
            make_document(
                REPRESENTATION_TRANSLATION_SCHEMA,
                translation.as_dict(),
            )
        )

    def compile_collective_synthesis(
        self,
        synthesis: CollectiveSynthesis,
    ) -> MethodCompositionResult:
        if not isinstance(synthesis, CollectiveSynthesis):
            raise CollectiveHiveError("collective synthesis has the wrong type")
        request = CollaborationRequest.from_dict(
            self._require_collaboration_artifact(
                COLLABORATION_REQUEST_SCHEMA,
                "request_id",
                synthesis.request_id,
            )
        )
        responses = tuple(
            CollaborationResponse.from_dict(
                self._require_collaboration_artifact(
                    COLLABORATION_RESPONSE_SCHEMA,
                    "response_id",
                    response_id,
                )
            )
            for response_id in synthesis.response_ids
        )
        for response in responses:
            assignment = CollaborationAssignment.from_dict(
                self._require_collaboration_artifact(
                    COLLABORATION_ASSIGNMENT_SCHEMA,
                    "assignment_id",
                    response.assignment_id,
                )
            )
            if assignment.request_id != synthesis.request_id:
                raise CollectiveHiveError(
                    "synthesis response belongs to another request"
                )
        translations = tuple(
            RepresentationTranslation.from_dict(
                self._require_collaboration_artifact(
                    REPRESENTATION_TRANSLATION_SCHEMA,
                    "translation_id",
                    translation_id,
                )
            )
            for translation_id in synthesis.translation_ids
        )
        response_ids = {response.response_id for response in responses}
        if any(
            translation.source_response_id not in response_ids
            for translation in translations
        ):
            raise CollectiveHiveError(
                "synthesis translation belongs to an omitted response"
            )
        return compile_collaborative_method(
            request,
            responses,
            translations,
            synthesis,
        )

    def record_collective_synthesis(self, synthesis: CollectiveSynthesis) -> str:
        self.compile_collective_synthesis(synthesis)
        return self.store.put_document(
            make_document(COLLECTIVE_SYNTHESIS_SCHEMA, synthesis.as_dict())
        )

    def record_affect_report(self, report: AffectReport) -> str:
        if not isinstance(report, AffectReport):
            raise CollectiveHiveError("affect report has the wrong type")
        content = report.as_dict()
        for document in self.store.list_documents(schema=AFFECT_REPORT_SCHEMA):
            prior = document.get("content", {})
            if isinstance(prior, Mapping) and prior.get("message_id") == report.message_id:
                if prior != content:
                    raise CollectiveHiveError(
                        "affect report message identity was reused with changed content"
                    )
                return str(document["object_id"])
        return self.store.put_document(make_document(AFFECT_REPORT_SCHEMA, content))


    def list_collaboration(self, schema: str) -> tuple[Mapping[str, Any], ...]:
        if schema not in {
            COLLABORATION_REQUEST_SCHEMA,
            COLLABORATION_ASSIGNMENT_SCHEMA,
            COLLABORATION_RESPONSE_SCHEMA,
            REPRESENTATION_TRANSLATION_SCHEMA,
            COLLECTIVE_SYNTHESIS_SCHEMA,
            AFFECT_REPORT_SCHEMA,
        }:
            raise CollectiveHiveError("unsupported collaboration schema")
        return self.store.list_documents(schema=schema)

    def consolidate(self, capsules: Sequence[ExperienceCapsule], *, valid_for_ns: int | None = None) -> tuple[ConsolidatedMemory, ...]:
        return self.memories.consolidate(capsules, valid_for_ns=valid_for_ns)





def compose_field_programs(
    programs: Sequence[FieldProgram],
    *,
    program_id: str,
    bindings: Mapping[str, str] | None = None,
    maximum_steps: int = 256,
    maximum_prefix_code_bits: int = 4096,
) -> FieldProgram:
    """Compose a local sequential program; Hive graphs use checked interfaces."""

    if isinstance(programs, (str, bytes)) or not programs:
        raise CollectiveHiveError("program composition requires at least one program")
    if any(not isinstance(program, FieldProgram) for program in programs):
        raise CollectiveHiveError("program composition accepts FieldProgram values")
    _text(program_id, "program_id")
    if maximum_steps < 1 or maximum_prefix_code_bits < 1:
        raise CollectiveHiveError("composition budgets must be positive")
    mapping = dict(bindings or {})
    roles: list[str] = list(programs[0].roles)
    steps: list[PrimitiveStep] = list(programs[0].steps)
    available = set(roles) | {step.output for step in steps}
    dependencies: list[str] = [
        programs[0].program_id,
        *programs[0].dependencies,
    ]
    for program in programs[1:]:
        dependencies.extend([program.program_id, *program.dependencies])
        for role in program.roles:
            if role not in available and role not in mapping:
                roles.append(role)
                available.add(role)
        for step in program.steps:
            inputs = tuple(mapping.get(item, item) for item in step.inputs)
            if any(item not in available for item in inputs):
                raise CollectiveHiveError(
                    f"composition input {inputs!r} is not bound"
                )
            output = f"{program.program_id}:{step.output}"
            steps.append(
                PrimitiveStep(
                    operation=step.operation,
                    output=output,
                    inputs=inputs,
                    literal=step.literal,
                )
            )
            available.add(output)
        local_outputs = {step.output for step in program.steps}
        mapping = {
            key: (
                f"{program.program_id}:{value}"
                if value in local_outputs
                else value
            )
            for key, value in mapping.items()
        }
    outputs = tuple(
        f"{programs[-1].program_id}:{output}"
        if len(programs) > 1
        else output
        for output in programs[-1].outputs
    )
    if len(steps) > maximum_steps:
        raise CollectiveHiveError("composed program exceeds maximum step budget")
    prefix_bits = sum(program.prefix_code_bits for program in programs)
    if prefix_bits > maximum_prefix_code_bits:
        raise CollectiveHiveError("composed program exceeds prefix-code budget")
    return FieldProgram(
        program_id=program_id,
        version=1,
        roles=tuple(dict.fromkeys(roles)),
        steps=tuple(steps),
        outputs=outputs,
        guards=tuple(programs[0].guards),
        support_event_ids=tuple(
            dict.fromkeys(
                event_id
                for program in programs
                for event_id in program.support_event_ids
            )
        ),
        dependencies=tuple(dict.fromkeys(dependencies)),
        known_exceptions=tuple(
            dict.fromkeys(
                exception
                for program in programs
                for exception in program.known_exceptions
            )
        ),
        prefix_code_bits=prefix_bits,
        status="candidate",
    )


__all__ = [
    "AFFECT_REPORT_SCHEMA",
    "AffectReport",
    "AdaptationFork",
    "AdaptationManager",
    "COLLABORATION_ASSIGNMENT_SCHEMA",
    "COLLABORATION_REQUEST_SCHEMA",
    "COLLABORATION_RESPONSE_SCHEMA",
    "COLLECTIVE_SYNTHESIS_SCHEMA",
    "EXECUTABLE_METHOD_SCHEMA",
    "ExecutableMethod",
    "METHOD_COMPOSITION_RESULT_SCHEMA",
    "METHOD_COMPOSITION_SCHEMA",
    "METHOD_INTERFACE_SCHEMA",
    "MethodCompositionResult",
    "MethodCompositionSpec",
    "MethodConnection",
    "MethodInterface",
    "MethodOutputBinding",
    "MethodPort",
    "CollaborationAssignment",
    "CollaborationRequest",
    "CollaborationResponse",
    "CollectiveSynthesis",
    "COLLECTIVE_SCHEMA",
    "CollectiveHive",
    "CollectiveHiveError",
    "ConsolidatedMemory",
    "DiversityProfile",
    "DiversitySelector",
    "EXPIRATION_SCHEMA",
    "HiveOffer",
    "HiveQuery",
    "HypothesisEdge",
    "HypothesisGraph",
    "HypothesisNode",
    "IDENTITY_SCHEMA",
    "IndependenceReport",
    "InstanceIdentity",
    "MemoryConsolidator",
    "OutcomeEvidence",
    "OutcomeMetric",
    "OFFER_SCHEMA",
    "QUERY_SCHEMA",
    "QuorumReport",
    "ReputationLedger",
    "REPUTATION_SCHEMA",
    "REPRESENTATION_TRANSLATION_SCHEMA",
    "RepresentationTranslation",
    "ReviewerProfile",
    "RoleAssignment",
    "RoleRouter",
    "SPECIALIST_ROLES",
    "check_reviewer_independence",
    "compile_collaborative_method",
    "compose_field_programs",
    "weighted_quorum",
]
