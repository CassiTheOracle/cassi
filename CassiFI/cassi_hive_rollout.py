"""Run one promoted field program across independent live Hive members.

A population rollout is deliberately sequential and owner-backed: every member
gets its own persistent field home and profile, adopts through ``HiveField``,
records held-out evidence, and contributes a receipt to one population ledger.
The shared hive stores semantic receipts only; adaptive field state remains in
each member's owner home.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_hive_collective import (
    CollectiveHive,
    CollectiveHiveError,
    ExecutionAssessment,
    PopulationMemberComparison,
    PopulationMemberOutcome,
    PopulationOutcomeLedger,
    PopulationRoundLedger,
    PopulationRoundRecord,
)
from cassi_hive_runtime import HiveField, HiveRuntimeError
from cassi_hive_store import HiveStoreError, LocalHiveStore


class PopulationRolloutError(ValueError):
    """Raised when a population rollout cannot satisfy its shared contract."""


def _text(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > 512
        or any(ord(character) < 32 for character in value)
    ):
        raise PopulationRolloutError(f"{label} must be bounded nonempty text")
    return value


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PopulationRolloutError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _failure_text(error: BaseException) -> str:
    message = " ".join(str(error).split()) or type(error).__name__
    encoded = message.encode("utf-8")
    if len(encoded) <= 512:
        return message
    return encoded[:509].decode("utf-8", errors="ignore") + "..."


@dataclass(frozen=True, slots=True)
class MemberRolloutSpec:
    """Immutable reference to one independently executed member assessment."""

    instance_id: str
    field_home: Path
    field_profile_sha256: str
    assessment_id: str

    def __post_init__(self) -> None:
        _text(self.instance_id, "member instance_id")
        try:
            field_home = Path(self.field_home)
        except TypeError as exc:
            raise PopulationRolloutError(
                "member field_home must be path-like"
            ) from exc
        if not str(field_home):
            raise PopulationRolloutError(
                "member field_home must be nonempty"
            )
        object.__setattr__(self, "field_home", field_home)
        _digest(self.field_profile_sha256, "member field profile")
        _digest(self.assessment_id, "member execution assessment")


class PopulationRollout:
    """Apply one verified bundle to multiple independent live field owners."""

    def __init__(self, store: LocalHiveStore, *, hive_id: str = "main", branch: str = "main") -> None:
        if not isinstance(store, LocalHiveStore):
            raise PopulationRolloutError("population rollout requires LocalHiveStore")
        self.store = store
        self.hive_id = _text(hive_id, "hive_id")
        self.branch = _text(branch, "branch")
        self.collective = CollectiveHive(store)

    def run(
        self,
        bundle_id: str,
        *,
        protocol_sha256: str,
        members: Sequence[MemberRolloutSpec],
        created_ns: int | None = None,
    ) -> PopulationOutcomeLedger:
        """Adopt ``bundle_id`` in every member and persist one population ledger.

        Invalid rollout inputs fail before any field is opened.  Member-local
        adoption failures are retained in the ledger and do not erase successful
        receipts from other members, making partial population coverage visible.
        """
        _digest(bundle_id, "bundle_id")
        _digest(protocol_sha256, "protocol_sha256")
        specs = self._validate_members(members)
        assessments = self._assessments(
            bundle_id,
            protocol_sha256,
            specs,
        )
        results = tuple(
            self._run_member(bundle_id, spec, assessment)
            for spec, assessment in zip(specs, assessments, strict=True)
        )
        ledger = PopulationOutcomeLedger(
            bundle_id=bundle_id,
            protocol_sha256=protocol_sha256,
            members=results,
            held_out=assessments[0].held_out,
            created_ns=time.time_ns() if created_ns is None else created_ns,
        )
        try:
            self.collective.record_population_ledger(ledger)
        except CollectiveHiveError as exc:
            raise PopulationRolloutError("population ledger could not be recorded") from exc
        return ledger

    @staticmethod
    def _validate_members(members: Sequence[MemberRolloutSpec]) -> tuple[MemberRolloutSpec, ...]:
        if isinstance(members, (str, bytes)):
            raise PopulationRolloutError("members must be a nonempty sequence")
        try:
            specs = tuple(members)
        except TypeError as exc:
            raise PopulationRolloutError("members must be a nonempty sequence") from exc
        if not specs or any(not isinstance(spec, MemberRolloutSpec) for spec in specs):
            raise PopulationRolloutError("members must contain MemberRolloutSpec values")
        instance_ids = tuple(spec.instance_id for spec in specs)
        if len(instance_ids) != len(set(instance_ids)):
            raise PopulationRolloutError("member instance IDs must be unique")
        profiles = tuple(spec.field_profile_sha256 for spec in specs)
        if len(profiles) != len(set(profiles)):
            raise PopulationRolloutError("member field profiles must be distinct")
        homes = tuple(str(spec.field_home.resolve()) for spec in specs)
        if len(homes) != len(set(homes)):
            raise PopulationRolloutError("member field homes must be distinct")
        return specs

    def _assessments(
        self,
        bundle_id: str,
        protocol_sha256: str,
        specs: Sequence[MemberRolloutSpec],
    ) -> tuple[ExecutionAssessment, ...]:
        assessments: list[ExecutionAssessment] = []
        for spec in specs:
            try:
                document = self.store.get_document(spec.assessment_id)
                assessment = ExecutionAssessment.from_document(document)
            except (HiveStoreError, CollectiveHiveError) as exc:
                raise PopulationRolloutError(
                    "member execution assessment is unavailable or invalid"
                ) from exc
            if assessment.object_id != spec.assessment_id:
                raise PopulationRolloutError(
                    "member execution assessment identity mismatch"
                )
            if (
                assessment.bundle_id != bundle_id
                or assessment.protocol_sha256 != protocol_sha256
                or assessment.recipient_instance_id != spec.instance_id
            ):
                raise PopulationRolloutError(
                    "member execution assessment does not match the rollout"
                )
            for trace_id in assessment.trace_document_ids:
                try:
                    self.store.get_document(trace_id)
                except HiveStoreError as exc:
                    raise PopulationRolloutError(
                        "member execution trace is unavailable"
                    ) from exc
            assessments.append(assessment)
        held_out = {assessment.held_out for assessment in assessments}
        if len(held_out) != 1:
            raise PopulationRolloutError(
                "member held-out settings must agree"
            )
        metric_names = tuple(
            metric.name for metric in assessments[0].metrics
        )
        for assessment in assessments[1:]:
            if tuple(metric.name for metric in assessment.metrics) != metric_names:
                raise PopulationRolloutError(
                    "member metric names must agree"
                )
        return tuple(assessments)

    def _run_member(
        self,
        bundle_id: str,
        spec: MemberRolloutSpec,
        assessment: ExecutionAssessment,
    ) -> PopulationMemberOutcome:
        try:
            with HiveField.open(
                spec.field_home,
                hive=self.store,
                hive_id=self.hive_id,
                branch=self.branch,
                instance_id=spec.instance_id,
                role="member",
                mode="member",
                apply_mode="verified",
                sync_mode="manual",
                profile_sha256=spec.field_profile_sha256,
                metadata={"population_rollout": True},
            ) as member:
                report, outcome = member.adopt_and_record_outcome(
                    bundle_id,
                    assessment_id=spec.assessment_id,
                )
                adoption_status = "replayed" if bundle_id in report.replayed else "accepted"
                return PopulationMemberOutcome(
                    instance_id=spec.instance_id,
                    field_profile_sha256=spec.field_profile_sha256,
                    adoption_status=adoption_status,
                    outcome_success=outcome.success,
                    score=outcome.score,
                    adoption_receipt_id=outcome.adoption_receipt_id,
                    outcome_id=outcome.object_id,
                    adopted_program_ids=tuple(row.program_id for row in member.raw_owner.state.programs),
                    post_state_sha256=member.raw_owner.state.state_sha256,
                    report=report.as_dict(),
                    held_out=assessment.held_out,
                )
        except (HiveRuntimeError, HiveStoreError, OSError, CollectiveHiveError) as exc:
            return PopulationMemberOutcome(
                instance_id=spec.instance_id,
                field_profile_sha256=spec.field_profile_sha256,
                adoption_status="failed",
                outcome_success=None,
                score=None,
                report={},
                error=_failure_text(exc),
                held_out=assessment.held_out,
            )


@dataclass(frozen=True, slots=True)
class PopulationRoundSpec:
    """One verified bundle round in a successive rollout campaign."""

    bundle_id: str
    protocol_sha256: str
    members: tuple[MemberRolloutSpec, ...]
    reviewer_predictions: Mapping[str, float] = ()
    independent_reviewer_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _digest(self.bundle_id, "round bundle_id")
        _digest(self.protocol_sha256, "round protocol_sha256")
        if isinstance(self.members, (str, bytes)):
            raise PopulationRolloutError("round members must be a nonempty sequence")
        try:
            members = tuple(self.members)
        except TypeError as exc:
            raise PopulationRolloutError("round members must be a nonempty sequence") from exc
        if not members or any(not isinstance(member, MemberRolloutSpec) for member in members):
            raise PopulationRolloutError("round members must contain MemberRolloutSpec values")
        object.__setattr__(self, "members", members)
        raw_predictions = {} if self.reviewer_predictions == () else self.reviewer_predictions
        if not isinstance(raw_predictions, Mapping):
            raise PopulationRolloutError("round reviewer_predictions must be a mapping")
        predictions = {}
        for reviewer_id, value in raw_predictions.items():
            _text(reviewer_id, "round reviewer ID")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
                raise PopulationRolloutError("round reviewer predictions must be in [0, 1]")
            predictions[reviewer_id] = float(value)
        object.__setattr__(self, "reviewer_predictions", predictions)
        if isinstance(self.independent_reviewer_ids, (str, bytes)):
            raise PopulationRolloutError("round independent reviewer IDs must be a sequence")
        independent = tuple(_text(item, "round independent reviewer ID") for item in self.independent_reviewer_ids)
        if len(independent) != len(set(independent)):
            raise PopulationRolloutError("round independent reviewer IDs must be unique")
        if not set(independent).issubset(predictions):
            raise PopulationRolloutError("round independent reviewers need predictions")
        object.__setattr__(self, "independent_reviewer_ids", independent)


class MultiRoundPopulationRollout:
    """Roll successive bundles through the same independent member population."""

    def __init__(
        self,
        store: LocalHiveStore,
        *,
        hive_id: str = "main",
        branch: str = "main",
        reviewer_profiles: Mapping[str, Any] | None = None,
    ) -> None:
        self.rollout = PopulationRollout(store, hive_id=hive_id, branch=branch)
        self.collective = self.rollout.collective
        self.reviewer_profiles = dict(reviewer_profiles or {})
        self._round_records: list[PopulationRoundRecord] = []
        self._member_keys: Mapping[str, tuple[str, str]] | None = None
        self._metric_names: tuple[str, ...] | None = None
        self._previous_local_scores: dict[str, float | None] = {}
        self._previous_population_score: float | None = None
        self._final_ledger: PopulationRoundLedger | None = None

    def run_round(self, spec: PopulationRoundSpec) -> PopulationRoundRecord:
        if self._final_ledger is not None:
            raise PopulationRolloutError("round campaign is already finalized")
        if not isinstance(spec, PopulationRoundSpec):
            raise PopulationRolloutError("round requires PopulationRoundSpec")
        members = PopulationRollout._validate_members(spec.members)
        assessments = self.rollout._assessments(
            spec.bundle_id,
            spec.protocol_sha256,
            members,
        )
        keys = {
            member.instance_id: (str(member.field_home.resolve()), member.field_profile_sha256)
            for member in members
        }
        metric_names = tuple(metric.name for metric in assessments[0].metrics)
        if self._member_keys is None:
            self._member_keys = keys
            self._metric_names = metric_names
        elif keys != self._member_keys:
            raise PopulationRolloutError("successive rounds must use the same member homes and profiles")
        elif metric_names != self._metric_names:
            raise PopulationRolloutError("successive rounds must use the same metric names")

        population = self.rollout.run(
            spec.bundle_id,
            protocol_sha256=spec.protocol_sha256,
            members=members,
        )
        calibrated_reviewer_ids: tuple[str, ...] = ()
        if spec.reviewer_predictions:
            if not self.reviewer_profiles:
                raise PopulationRolloutError("reviewer predictions require reviewer profiles")
            try:
                calibrated = self.collective.calibrate_population(
                    population,
                    self.reviewer_profiles,
                    predicted_support=spec.reviewer_predictions,
                    independent_ids=spec.independent_reviewer_ids,
                )
            except CollectiveHiveError as exc:
                raise PopulationRolloutError("population evidence could not calibrate reviewers") from exc
            self.reviewer_profiles.update(calibrated)
            calibrated_reviewer_ids = tuple(sorted(calibrated))

        previous_population_score = self._previous_population_score
        comparisons: list[PopulationMemberComparison] = []
        for member in population.members:
            previous_local_score = self._previous_local_scores.get(member.instance_id)
            local_score = member.score
            population_score = population.population_score
            comparisons.append(
                PopulationMemberComparison(
                    instance_id=member.instance_id,
                    local_score=local_score,
                    population_score=population_score,
                    local_minus_population=(
                        None
                        if local_score is None or population_score is None
                        else local_score - population_score
                    ),
                    previous_local_score=previous_local_score,
                    local_score_delta=(
                        None
                        if local_score is None or previous_local_score is None
                        else local_score - previous_local_score
                    ),
                    population_score_delta=(
                        None
                        if population_score is None or previous_population_score is None
                        else population_score - previous_population_score
                    ),
                    outcome_success=member.outcome_success,
                )
            )
            self._previous_local_scores[member.instance_id] = local_score
        self._previous_population_score = population.population_score
        record = PopulationRoundRecord(
            round_index=len(self._round_records),
            bundle_id=spec.bundle_id,
            protocol_sha256=spec.protocol_sha256,
            population_ledger_id=population.object_id,
            status=population.status,
            population_score=population.population_score,
            outcome_coverage=population.outcome_coverage,
            comparisons=tuple(comparisons),
            calibrated_reviewer_ids=calibrated_reviewer_ids,
            reviewer_predictions=spec.reviewer_predictions,
            outcome_ids=tuple(
                member.outcome_id
                for member in population.members
                if member.outcome_id is not None
            ),
        )
        self._round_records.append(record)
        return record

    def finalize(self, *, created_ns: int | None = None) -> PopulationRoundLedger:
        if self._final_ledger is not None:
            return self._final_ledger
        if not self._round_records:
            raise PopulationRolloutError("round campaign needs at least one completed round")
        ledger = PopulationRoundLedger(
            rounds=tuple(self._round_records),
            created_ns=time.time_ns() if created_ns is None else created_ns,
        )
        try:
            self.collective.record_round_ledger(ledger)
        except CollectiveHiveError as exc:
            raise PopulationRolloutError("round comparison ledger could not be recorded") from exc
        self._final_ledger = ledger
        return ledger

    def run(
        self,
        rounds: Sequence[PopulationRoundSpec],
        *,
        created_ns: int | None = None,
    ) -> PopulationRoundLedger:
        if isinstance(rounds, (str, bytes)):
            raise PopulationRolloutError("rounds must be a nonempty sequence")
        try:
            specs = tuple(rounds)
        except TypeError as exc:
            raise PopulationRolloutError("rounds must be a nonempty sequence") from exc
        if not specs:
            raise PopulationRolloutError("rounds must be a nonempty sequence")
        for spec in specs:
            self.run_round(spec)
        return self.finalize(created_ns=created_ns)
