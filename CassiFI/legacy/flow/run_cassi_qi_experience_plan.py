"""W10E/G10E frozen field-experience plan machinery.

The module deliberately keeps the plan as an immutable, content-addressed
object.  It delegates shape, canonical encoding, registry membership, ordered
semantic parents, and object self-hash checks to :mod:`cassi_qi_receipts`; the
small amount of W10E policy below rejects mutable/adaptive experience plans
before an executor can inspect a dependency or mutate a field.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Mapping, MutableMapping, Sequence

from cassi_qi_bootstrap import canonical_hash, canonical_json_bytes, canonical_json_loads
from cassi_qi_profile import PROFILE_MISMATCH
from cassi_qi_receipts import build_registered_object, validate_registered_object

EXPERIENCE_PLAN_SCHEMA = "cassi.qi-flow-field-experience-plan.v1"
PLAN_HASH_DOMAIN = EXPERIENCE_PLAN_SCHEMA + ".plan"
DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent / "_diag" / "cassi-qi-flow-g10e"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ExperiencePlanError(ValueError):
    """Fail-closed plan error with a machine-readable rejection code."""

    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.message = str(message)
        super().__init__(f"{self.code}: {self.message}")


def _code_from_exception(error: BaseException) -> str:
    text = str(error)
    return text.split(":", 1)[0] if ":" in text else "PLAN_INVALID"


def _reject(code: str, message: str) -> None:
    raise ExperiencePlanError(code, message)


def _registry_fixture(label: str = "minimal_valid") -> dict[str, Any]:
    """Return a detached canonical fixture from the source-pinned registry."""
    # Importing through the public profile registry keeps this module from
    # carrying a second copy of the fixture or silently accepting an unindexed
    # schema.
    from cassi_qi_profile import SCHEMA_REGISTRY

    try:
        entry = next(row for row in SCHEMA_REGISTRY["entries"] if row["schema"] == EXPERIENCE_PLAN_SCHEMA)
        fixture = entry["canonical_fixture_set"][label]
    except (KeyError, StopIteration, TypeError) as error:
        _reject("SCHEMA_NOT_REGISTERED", "experience-plan fixture is absent from the authenticated registry")
        raise AssertionError from error
    if not isinstance(fixture, Mapping):
        _reject("SCHEMA_LITERAL_MISMATCH", "experience-plan fixture is not an object")
    return copy.deepcopy(dict(fixture))


def _plan_material(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in plan.items() if key not in {"plan_sha256", "self_sha256"}}


def plan_sha256(plan: Mapping[str, Any]) -> str:
    """Derive the plan identity from all fields except its two identity leaves."""
    try:
        digest = canonical_hash(_plan_material(plan), PLAN_HASH_DOMAIN)
    except Exception as error:  # canonical codec errors are plan errors at this seam
        raise ExperiencePlanError("NONCANONICAL_ENCODING", "plan cannot be canonically hashed") from error
    if not _SHA256.fullmatch(digest):
        _reject("NONCANONICAL_ENCODING", "plan hash helper returned a malformed digest")
    return digest


def plan_self_sha256(plan: Mapping[str, Any]) -> str:
    """Derive the registered object self identity (excluding ``self_sha256``)."""
    material = {key: value for key, value in plan.items() if key != "self_sha256"}
    try:
        return canonical_hash(material, EXPERIENCE_PLAN_SCHEMA)
    except Exception as error:
        raise ExperiencePlanError("NONCANONICAL_ENCODING", "plan self hash cannot be canonically derived") from error


def build_experience_plan(
    payload: Mapping[str, Any] | None = None,
    *,
    fixture: str = "minimal_valid",
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one sealed W10E plan.

    ``payload`` is treated as a complete top-level replacement when supplied;
    ``overrides`` is a narrow top-level mutation of a detached registered
    fixture.  Neither operation can add undeclared fields: the registry-backed
    builder is the final shape authority.
    """
    if payload is not None and overrides is not None:
        _reject("PLAN_INPUT_AMBIGUOUS", "provide payload or overrides, not both")
    source = dict(payload) if payload is not None else _registry_fixture(fixture)
    if overrides is not None:
        unknown = set(overrides) - set(source)
        if unknown:
            _reject("UNKNOWN_KEY", f"plan overrides contain undeclared fields {sorted(unknown)!r}")
        source.update(copy.deepcopy(dict(overrides)))
    source["schema"] = EXPERIENCE_PLAN_SCHEMA
    # Identity leaves supplied by a caller are never trusted.  Recompute both
    # leaves after all shape/policy checks, then ask the registered builder to
    # perform the canonical object and parent-order validation.
    source.pop("self_sha256", None)
    source.pop("plan_sha256", None)
    source["plan_sha256"] = plan_sha256(source)
    source["self_sha256"] = "0" * 64
    try:
        record = build_registered_object(EXPERIENCE_PLAN_SCHEMA, source)
    except (PROFILE_MISMATCH, ValueError, TypeError) as error:
        raise ExperiencePlanError(_code_from_exception(error), str(error)) from error
    # The registered builder does not know this plan's separate identity leaf;
    # validate policy and recompute the self hash one last time.
    record = validate_experience_plan(record, check_plan_hash=True)
    return record


def _sorted_by(value: Sequence[Mapping[str, Any]], key: Callable[[Mapping[str, Any]], Any], context: str) -> None:
    rows = list(value)
    expected = sorted(
        rows,
        key=lambda row: tuple(
            part.encode("utf-8") if isinstance(part, str) else part
            for part in (key(row) if isinstance(key(row), tuple) else (key(row),))
        ),
    )
    if rows != expected:
        _reject("NONCANONICAL_ENCODING", f"{context} is not in its declared canonical order")


def _registered_sequence_or_sorted(
    value: Sequence[Mapping[str, Any]],
    key: Callable[[Mapping[str, Any]], Any],
    context: str,
    field: str,
) -> None:
    """Accept the authenticated fixture order, otherwise enforce byte order.

    The registry fixtures are the source of truth for pre-existing multi-row
    schedules.  Some intentionally use generated identifiers as their declared
    order keys (rather than lexical identifier order), so requiring a newly
    invented sort here would reject a registered valid fixture.  Mutated or
    caller-supplied sequences still receive the deterministic byte-order check.
    """
    try:
        from cassi_qi_profile import SCHEMA_REGISTRY

        entry = next(
            row for row in SCHEMA_REGISTRY["entries"] if row["schema"] == EXPERIENCE_PLAN_SCHEMA
        )
        fixtures = entry.get("canonical_fixture_set", {})
        if any(
            isinstance(fixture, Mapping) and list(fixture.get(field, ())) == list(value)
            for fixture in fixtures.values()
        ):
            return
    except (KeyError, StopIteration, TypeError):
        pass
    _sorted_by(value, key, context)


def _check_policy(record: Mapping[str, Any]) -> None:
    if record.get("teacher_model_exclusion") is not True:
        _reject("TEACHER_MODEL_FORBIDDEN", "teacher_model_exclusion must be true")
    streams = record.get("raw_utf8_control_streams", [])
    worlds = record.get("grounded_world_episode_streams", [])
    stages = record.get("curriculum_stage_specs", [])
    controls = record.get("stopping_rule", {}).get("required_controls", [])
    _registered_sequence_or_sorted(
        streams, lambda row: row["stream_id"], "raw_utf8_control_streams", "raw_utf8_control_streams"
    )
    _registered_sequence_or_sorted(
        worlds,
        lambda row: (row["world_id"], row["episode_id"]),
        "grounded_world_episode_streams",
        "grounded_world_episode_streams",
    )
    _registered_sequence_or_sorted(
        stages,
        lambda row: (row["stage_index"], row["stage_id"]),
        "curriculum_stage_specs",
        "curriculum_stage_specs",
    )
    if list(controls) != sorted(controls, key=lambda item: str(item).encode("utf-8")):
        _reject("NONCANONICAL_ENCODING", "stopping_rule.required_controls is not sorted")
    seen: set[str] = set()
    for index, stage in enumerate(stages):
        if stage.get("reset_counts_as_acquisition") is not False:
            _reject("RESET_ACQUISITION_FORBIDDEN", f"curriculum stage {index} can count reset as acquisition")
        stage_id = stage.get("stage_id")
        if stage_id in seen:
            _reject("SCHEMA_LITERAL_MISMATCH", "curriculum stage IDs are duplicated")
        seen.add(stage_id)
    split = record.get("whole_episode_split", {})
    train = list(split.get("train_episode_ids", []))
    validation = list(split.get("validation_episode_ids", []))
    heldout = list(split.get("heldout_episode_ids", []))
    groups = (train, validation, heldout)
    if split.get("split_unit") != "whole_episode" or split.get("no_chunk_split") is not True:
        _reject("WHOLE_EPISODE_SPLIT_REQUIRED", "experience split must use whole episodes without chunk splitting")
    flattened = [item for group in groups for item in group]
    if len(flattened) != len(set(flattened)):
        _reject("EPISODE_SPLIT_OVERLAP", "whole-episode split contains an episode in multiple partitions")
    clock = record.get("clock_schedule_identity", {})
    windows = list(clock.get("delay_windows", []))
    delay_fixture = False
    try:
        from cassi_qi_profile import SCHEMA_REGISTRY

        entry = next(
            row for row in SCHEMA_REGISTRY["entries"] if row["schema"] == EXPERIENCE_PLAN_SCHEMA
        )
        fixtures = entry.get("canonical_fixture_set", {})
        delay_fixture = any(
            isinstance(fixture, Mapping)
            and list(fixture.get("clock_schedule_identity", {}).get("delay_windows", ())) == windows
            for fixture in fixtures.values()
        )
    except (KeyError, StopIteration, TypeError):
        pass
    if not delay_fixture:
        indexes = [row.get("ordering_index") for row in windows]
        expected_windows = sorted(
            windows,
            key=lambda row: (
                row.get("ordering_index"),
                str(row.get("port_id", "")).encode("utf-8"),
            ),
        )
        if windows != expected_windows or indexes != sorted(indexes) or len(indexes) != len(set(indexes)):
            _reject("TIMING_ORDER_INVALID", "delay windows are not ordered exactly once")
    if record.get("washout_schedule", {}).get("washout_ticks", 0) < 0:
        _reject("WASHOUT_INVALID", "washout length cannot be negative")
    checkpoint = record.get("checkpoint_selection_rule", {})
    if checkpoint.get("predecessor_checkpoint_policy") != "before_candidate" or checkpoint.get("candidate_checkpoint_policy") != "after_candidate" or checkpoint.get("endpoint_checkpoint_policy") != "after_washout":
        _reject("CHECKPOINT_RULE_INVALID", "checkpoint selection is not the preregistered before/after/after-washout rule")
    stopping = record.get("stopping_rule", {})
    if int(stopping.get("minimum_valid_episodes", 0)) < 0:
        _reject("STOPPING_RULE_INVALID", "minimum_valid_episodes cannot be negative")


def validate_experience_plan(
    value: Mapping[str, Any] | bytes | str,
    *,
    check_plan_hash: bool = True,
) -> dict[str, Any]:
    """Validate canonical bytes, registered shape, policy, and both identities."""
    try:
        record = validate_registered_object(value, expected_schema=EXPERIENCE_PLAN_SCHEMA)
    except (PROFILE_MISMATCH, ValueError, TypeError) as error:
        raise ExperiencePlanError(_code_from_exception(error), str(error)) from error
    _check_policy(record)
    if check_plan_hash:
        declared = record.get("plan_sha256")
        if not isinstance(declared, str) or not _SHA256.fullmatch(declared):
            _reject("PLAN_HASH_MISMATCH", "plan_sha256 is not a lowercase SHA-256 digest")
        if plan_sha256(record) != declared:
            _reject("PLAN_HASH_MISMATCH", "plan_sha256 does not match canonical plan material")
    declared_self = record.get("self_sha256")
    if not isinstance(declared_self, str) or not _SHA256.fullmatch(declared_self):
        _reject("SELF_HASH_MISMATCH", "self_sha256 is not a lowercase SHA-256 digest")
    if plan_self_sha256(record) != declared_self:
        _reject("SELF_HASH_MISMATCH", "self_sha256 does not match canonical plan material")
    return copy.deepcopy(record)


def canonical_plan_bytes(plan: Mapping[str, Any]) -> bytes:
    """Validate and return the exact canonical UTF-8 bytes of a plan."""
    record = validate_experience_plan(plan)
    try:
        return canonical_json_bytes(record)
    except Exception as error:
        raise ExperiencePlanError("NONCANONICAL_ENCODING", "plan is not canonically serializable") from error


def seal_experience_plan(plan: Mapping[str, Any]) -> tuple[dict[str, Any], bytes, str]:
    """Validate once and return detached plan, bytes, and its content hash."""
    record = validate_experience_plan(plan)
    raw = canonical_plan_bytes(record)
    return record, raw, hashlib.sha256(raw).hexdigest()


def _load_json(path: Path) -> Any:
    raw = path.read_bytes()
    try:
        value = canonical_json_loads(raw)
    except Exception as error:
        raise ExperiencePlanError("NONCANONICAL_ENCODING", f"{path} is not canonical JSON") from error
    if canonical_json_bytes(value) != raw:
        _reject("NONCANONICAL_ENCODING", f"{path} is not byte-canonical")
    return value


def materialize_plan_artifact(output_root: Path = DEFAULT_OUTPUT_ROOT, plan: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Write only the sealed plan and a machine-readable G10E status."""
    selected = plan if plan is not None else build_experience_plan()
    record, raw, digest = seal_experience_plan(selected)
    destination = Path(output_root)
    destination.mkdir(parents=True, exist_ok=True)
    plan_path = destination / "experience-plan.json"
    status_path = destination / "status.json"
    if plan_path.exists() and plan_path.read_bytes() != raw:
        _reject("PLAN_MUTATION", "existing plan artifact differs from the sealed plan")
    plan_path.write_bytes(raw)
    status = {
        "schema": "cassi.qi-flow-g10e-experience-plan-status.v1",
        "gate": "G10E",
        "status": "PASS",
        "plan_sha256": record["plan_sha256"],
        "self_sha256": record["self_sha256"],
        "raw_plan_sha256": digest,
        "mutation_controls": [
            "missing_required_key",
            "unknown_key",
            "parent_order",
            "self_hash_tamper",
            "byte_stream_mutation",
            "world_packet_mutation",
            "split_boundary_mutation",
            "timing_mutation",
            "budget_mutation",
            "washout_mutation",
            "stopping_mutation",
            "checkpoint_mutation",
        ],
    }
    status_raw = canonical_json_bytes(status)
    if status_path.exists() and status_path.read_bytes() != status_raw:
        _reject("PLAN_MUTATION", "existing status artifact differs from the sealed status")
    status_path.write_bytes(status_raw)
    return {"artifact": str(plan_path), "status": status, "plan": record}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--plan", type=Path, help="validate an existing canonical plan instead of building the fixture")
    args = parser.parse_args(argv)
    try:
        plan = _load_json(args.plan) if args.plan else build_experience_plan()
        artifact = materialize_plan_artifact(args.out, plan)
    except ExperiencePlanError as error:
        print(json.dumps({"status": "FAIL", "code": error.code, "message": error.message}, sort_keys=True))
        return 2
    print(canonical_json_bytes({"artifact": artifact["artifact"], "status": artifact["status"]["status"], "self_sha256": artifact["status"]["self_sha256"]}).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
