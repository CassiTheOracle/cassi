"""High-level Cassi Hive runtime.

``HiveField`` connects one persistent field owner to a shared hive without
making the hive a second adaptive state.  It owns session identity, policy,
content-addressed export, staged/imported bundles, and adoption receipts while
all actual field mutations remain owner transactions.
"""

from __future__ import annotations

import json
import functools
import os
import shutil
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from cassi_field_atlas import ATLAS_SCHEMA, canonical_json_bytes, sha256_value
from cassi_field_hive import (
    AdoptionReceipt,
    ExperienceCandidate,
    ExperienceCapsule,
    ExperienceEvidence,
    HiveProtocolError,
    KnowledgeBundle,
    PORTABLE_PROFILE_SHA256,
    PORTABLE_TRANSFER_SCHEMA,
    capsule_from_owner_transition,
)
from cassi_hive_collective import (
    CollectiveHiveError,
    ExecutionAssessment,
    OutcomeEvidence,
)
from cassi_field_owner import CapacityLimits, FieldIntelligenceOwner
from cassi_hive_adapters import (
    DEFAULT_FIELD_PROFILE_SHA256,
    FieldAdapter,
    HiveAdapterError,
    PORTABLE_TRANSFER_SURFACE,
    adapt_owner,
)
from cassi_hive_policy import HivePolicyError, SkillPolicy
from cassi_hive_store import (
    DEFAULT_HIVE_HOME,
    EVENT_SCHEMA,
    FORK_SCHEMA,
    SESSION_SCHEMA,
    HiveStoreError,
    LocalHiveStore,
    decode_bundle,
    make_document,
)


RUNTIME_SCHEMA = "cassifi.hive.runtime.v1"
SESSION_STATE_SCHEMA = "cassifi.hive.session-state.v1"


class HiveRuntimeError(RuntimeError):
    """Raised when a connected field session cannot complete a hive operation."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or any(ord(char) < 32 for char in value):
        raise HiveRuntimeError(f"{label} must be bounded nonempty text")
    if len(value.encode("utf-8")) > 512:
        raise HiveRuntimeError(f"{label} is too large")
    return value


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise HiveRuntimeError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_json_bytes(value)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        encoded = path.read_bytes()
        value = json.loads(encoded.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HiveRuntimeError(f"cannot read canonical JSON from {path}") from exc
    if not isinstance(value, Mapping) or canonical_json_bytes(value) != encoded:
        raise HiveRuntimeError(f"{path} is not canonical JSON")
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class SessionIdentity:
    """Stable identity and provenance for one attached process."""

    hive_id: str
    branch: str
    instance_id: str
    session_id: str
    role: str
    field_profile_sha256: str
    atlas_schema: str = ATLAS_SCHEMA
    source_identity_sha256: str = sha256_value({"runtime": RUNTIME_SCHEMA})
    test_name: str = "unspecified"
    arm: str = "default"
    seed: int | None = None
    configuration_sha256: str = sha256_value({"configuration": {}})
    parent_instance_id: str | None = None
    metadata: Mapping[str, Any] = ()

    def __post_init__(self) -> None:
        for name in ("hive_id", "branch", "instance_id", "session_id", "role", "test_name", "arm"):
            _text(getattr(self, name), name)
        _digest(self.field_profile_sha256, "field_profile_sha256")
        _digest(self.source_identity_sha256, "source_identity_sha256")
        _digest(self.configuration_sha256, "configuration_sha256")
        if self.atlas_schema != ATLAS_SCHEMA:
            raise HiveRuntimeError("unsupported atlas schema")
        if self.seed is not None and (isinstance(self.seed, bool) or not isinstance(self.seed, int)):
            raise HiveRuntimeError("seed must be an integer or None")
        if self.parent_instance_id is not None:
            _text(self.parent_instance_id, "parent_instance_id")
        metadata = {} if self.metadata == () else self.metadata
        if not isinstance(metadata, Mapping):
            raise HiveRuntimeError("session metadata must be a mapping")
        object.__setattr__(self, "metadata", json.loads(canonical_json_bytes(metadata).decode("utf-8")))

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "arm": self.arm,
            "atlas_schema": self.atlas_schema,
            "branch": self.branch,
            "configuration_sha256": self.configuration_sha256,
            "field_profile_sha256": self.field_profile_sha256,
            "hive_id": self.hive_id,
            "instance_id": self.instance_id,
            "metadata": _plain(self.metadata),
            "parent_instance_id": self.parent_instance_id,
            "role": self.role,
            "seed": self.seed,
            "session_id": self.session_id,
            "source_identity_sha256": self.source_identity_sha256,
            "test_name": self.test_name,
        }


@dataclass(frozen=True, slots=True)
class SyncReport:
    """Observable result of one hive synchronization attempt."""

    staged: tuple[str, ...] = ()
    applied: tuple[str, ...] = ()
    replayed: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    blocked: tuple[str, ...] = ()
    errors: tuple[Mapping[str, Any], ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.applied or self.replayed)

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "applied": list(self.applied),
            "blocked": list(self.blocked),
            "changed": self.changed,
            "errors": [_plain(item) for item in self.errors],
            "replayed": list(self.replayed),
            "skipped": list(self.skipped),
            "staged": list(self.staged),
        }


@dataclass(frozen=True, slots=True)
class _SessionState:
    common_generation: int = 0
    staged_bundle_ids: tuple[str, ...] = ()
    adopted_bundle_ids: tuple[str, ...] = ()
    exported_capsule_ids: tuple[str, ...] = ()
    adoption_receipt_ids: tuple[str, ...] = ()

    def as_dict(self, *, session_id: str, instance_id: str, policy: SkillPolicy) -> Mapping[str, Any]:
        return {
            "adopted_bundle_ids": list(self.adopted_bundle_ids),
            "adoption_receipt_ids": list(self.adoption_receipt_ids),
            "common_generation": self.common_generation,
            "exported_capsule_ids": list(self.exported_capsule_ids),
            "instance_id": instance_id,
            "policy": policy.as_dict(),
            "schema": SESSION_STATE_SCHEMA,
            "session_id": session_id,
            "staged_bundle_ids": list(self.staged_bundle_ids),
        }


class SkillController:
    """Convenience surface for bundle discovery and policy toggles."""

    def __init__(self, field: "HiveField") -> None:
        self._field = field

    @property
    def policy(self) -> SkillPolicy:
        return self._field.policy

    @property
    def import_enabled(self) -> bool:
        return self.policy.import_enabled

    @property
    def export_enabled(self) -> bool:
        return self.policy.export_enabled

    def enable_import(self, *, apply_mode: str | None = None, sync_mode: str | None = None) -> SkillPolicy:
        return self._field.configure_exchange(import_skills=True, apply_mode=apply_mode, sync_mode=sync_mode)

    def disable_import(self) -> SkillPolicy:
        return self._field.configure_exchange(import_skills=False, apply_mode="never")

    def enable_export(self, *, export_mode: str | None = None) -> SkillPolicy:
        return self._field.configure_exchange(export_skills=True, export_mode=export_mode)

    def disable_export(self) -> SkillPolicy:
        return self._field.configure_exchange(export_skills=False)

    def available(self) -> tuple[Mapping[str, Any], ...]:
        return self._field.preview_imports()

    def pending(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(
            self._field.hive.get_document(bundle_id)
            for bundle_id in self._field._state.staged_bundle_ids
        )

    def preview(self, bundle_id: str) -> Mapping[str, Any]:
        return self._field.preview_bundle(bundle_id)

    def adopt(self, bundle_ids: Sequence[str] | None = None) -> SyncReport:
        return self._field.adopt(bundle_ids=bundle_ids)
    def adopt_and_record_outcome(
        self,
        bundle_id: str,
        *,
        assessment_id: str,
    ) -> tuple[SyncReport, OutcomeEvidence]:
        return self._field.adopt_and_record_outcome(
            bundle_id,
            assessment_id=assessment_id,
        )

    def sync(self) -> SyncReport:
        return self._field.sync()
    @property
    def collective(self) -> Any:
        return self._field.collective

    def query(self, query: Any) -> str:
        return self.collective.record_query(query)

    def publish_offer(self, offer: Any) -> str:
        return self.collective.publish_offer(offer)

    def record_outcome(self, outcome: Any) -> str:
        return self.collective.record_outcome(outcome)

    def consolidate(self, capsules: Sequence[ExperienceCapsule] | None = None, *, valid_for_ns: int | None = None) -> tuple[Any, ...]:
        rows = self._field.hive.list_capsules(hive_id=self._field.identity.hive_id) if capsules is None else tuple(capsules)
        return self.collective.consolidate(rows, valid_for_ns=valid_for_ns)


class _TrackedExperience:
    def __init__(self, field: "HiveField", kwargs: Mapping[str, Any]) -> None:
        self._field = field
        self._kwargs = dict(kwargs)
        self._committed: ExperienceCapsule | None = None

    def commit(self, *, transition: Mapping[str, Any]) -> ExperienceCapsule:
        if self._committed is not None:
            raise HiveRuntimeError("experience episode has already been committed")
        self._committed = self._field.publish_experience(transition=transition, **self._kwargs)
        return self._committed

    def __enter__(self) -> "_TrackedExperience":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


class _OwnerFacade:
    """Owner view that emits bounded capsules for committed transitions."""

    _LIFECYCLE_METHODS = frozenset({"close", "begin_transaction"})

    def __init__(self, field: "HiveField") -> None:
        self._field = field

    @property
    def raw(self) -> Any:
        return self._field._owner

    def __getattr__(self, name: str) -> Any:
        value = getattr(self.raw, name)
        if (
            name.startswith("_")
            or name in self._LIFECYCLE_METHODS
            or not callable(value)
        ):
            return value

        @functools.wraps(value)
        def invoke(*args: Any, **kwargs: Any) -> Any:
            return self._field._invoke_owner(name, value, args, kwargs)

        return invoke


def _bounded_owner_value(value: Any) -> Any:
    """Keep automatic capsule metadata canonical and bounded."""

    try:
        normalized = _plain(value)
        encoded = canonical_json_bytes(normalized)
    except Exception:
        representation = repr(value)
        return {
            "repr": representation[:256],
            "sha256": sha256_value({"repr": representation}),
            "type": type(value).__name__,
        }
    if len(encoded) <= 4096:
        return json.loads(encoded.decode("utf-8"))
    return {
        "bytes": len(encoded),
        "sha256": sha256_value({"encoded": encoded.hex()}),
        "type": type(value).__name__,
    }


class HiveField:
    """A local field owner connected to a durable Cassi Hive."""

    def __init__(
        self,
        *,
        owner: Any,
        adapter: FieldAdapter,
        hive: LocalHiveStore,
        identity: SessionIdentity,
        policy: SkillPolicy,
        field_home: Path,
        owns_owner: bool,
        owns_hive: bool,
    ) -> None:
        self._owner = owner
        self.adapter = adapter
        self._owner_facade = _OwnerFacade(self)
        self.hive = hive
        self.identity = identity
        self.policy = policy
        self.field_home = Path(field_home)
        self._owns_owner = owns_owner
        self._owns_hive = owns_hive
        self._state_path = self.field_home / "hive-session-state.json"
        self._state = self._load_state()
        self._collective: Any = None
        self.skills = SkillController(self)
        self.hive.register_session(
            make_document(SESSION_SCHEMA, identity.as_dict()),
            session_id=identity.session_id,
            instance_id=identity.instance_id,
            status="active",
        )
        self._save_state()

    @property
    def owner(self) -> Any:
        """Automatic-export facade over the underlying field owner."""

        return self._owner_facade

    @property
    def raw_owner(self) -> Any:
        """Underlying owner for explicit low-level/protocol operations."""

        return self.adapter.owner
    @property
    def collective(self) -> Any:
        if self._collective is None:
            from cassi_hive_collective import CollectiveHive

            self._collective = CollectiveHive(self.hive)
        return self._collective

    def _owner_head(self) -> Mapping[str, Any]:
        owner = self.adapter.owner
        return {
            "generation": owner.state.generation,
            "manifest_sha256": owner.checkpoints.current_manifest_sha256,
            "state_sha256": owner.state.state_sha256,
        }

    def _invoke_owner(
        self,
        method_name: str,
        method: Any,
        args: Sequence[Any],
        kwargs: Mapping[str, Any],
    ) -> Any:
        before = self._owner_head()
        result = method(*args, **dict(kwargs))
        after = self._owner_head()
        if (
            not self.policy.export_enabled
            or (
                before["manifest_sha256"] == after["manifest_sha256"]
                and before["state_sha256"] == after["state_sha256"]
            )
        ):
            return result

        operation = {
            "arguments": _bounded_owner_value({"args": list(args), "kwargs": dict(kwargs)}),
            "method": method_name,
        }
        operation_id = (
            str(result["operation_id"])
            if isinstance(result, Mapping) and "operation_id" in result
            else "hive-auto-" + sha256_value(
                {
                    "after": after["manifest_sha256"],
                    "before": before["manifest_sha256"],
                    "method": method_name,
                }
            )
        )
        if isinstance(result, Mapping) and {
            "operation_id",
            "manifest_sha256",
            "state_sha256",
            "predecessor_manifest_sha256",
            "generation",
        }.issubset(result):
            transition: Mapping[str, Any] = result
        else:
            transition = {
                "generation": after["generation"],
                "manifest_sha256": after["manifest_sha256"],
                "operation_id": operation_id,
                "predecessor_manifest_sha256": before["manifest_sha256"],
                "state_sha256": after["state_sha256"],
            }
        candidate_kind = "procedure"
        candidate_object: Mapping[str, Any] = operation
        candidate_plan: tuple[Mapping[str, Any], ...] = (
            {
                "arguments": operation["arguments"],
                "method": method_name,
                "operation": "owner-transition",
            },
        )
        if method_name == "configure_program":
            raw_program = kwargs.get("program")
            if raw_program is None and len(args) >= 2:
                raw_program = args[1]
            as_dict = getattr(raw_program, "as_dict", None)
            if callable(as_dict):
                program_payload = as_dict()
                if isinstance(program_payload, Mapping):
                    candidate_kind = "field-program"
                    candidate_object = {
                        "portable_transfer": True,
                        "program": dict(program_payload),
                    }
                    candidate_plan = (
                        {
                            "operation": "configure-program",
                            "program": dict(program_payload),
                        },
                    )
        candidate = ExperienceCandidate(
            kind=candidate_kind,
            object=candidate_object,
            operation_plan=candidate_plan,
            guards=(
                {
                    "predecessor_manifest_sha256": before["manifest_sha256"],
                    "predecessor_state_sha256": before["state_sha256"],
                },
            ),
            dependencies=(),
        )
        evidence = ExperienceEvidence(
            support_event_ids=(
                sha256_value({"method": method_name, "operation_id": operation_id}),
            ),
            assessment_ids=(
                sha256_value({"method": method_name, "state_sha256": after["state_sha256"]}),
            ),
            held_out_results=(
                {
                    "after_manifest_sha256": after["manifest_sha256"],
                    "after_state_sha256": after["state_sha256"],
                    "before_manifest_sha256": before["manifest_sha256"],
                    "before_state_sha256": before["state_sha256"],
                    "method": method_name,
                    "result": _bounded_owner_value(result),
                },
            ),
            counterexamples=(),
            derivation_roots=(),
        )
        try:
            self.publish_experience(
                transition=transition,
                task_id="hive-auto-" + method_name,
                context={
                    "automatic": True,
                    "field_profile_sha256": self.identity.field_profile_sha256,
                    "instance_id": self.identity.instance_id,
                    "method": method_name,
                },
                action=operation,
                prediction={
                    "operation_id": operation_id,
                    "predecessor_state_sha256": before["state_sha256"],
                },
                outcome={
                    "result": _bounded_owner_value(result),
                    "state_sha256": after["state_sha256"],
                },
                candidate=candidate,
                evidence=evidence,
                verify_checkpoints=False,
                predecessor_state_sha256=before["state_sha256"],
            )
        except Exception:
            # A revocation/rollback may intentionally make the predecessor
            # checkpoint un-loadable. The owner transition already committed;
            # automatic export is advisory unless the caller requested strict
            # availability through the policy.
            if self.policy.fail_if_unavailable:
                raise
        return result

    @classmethod
    def open(
        cls,
        field_home: Path,
        *,
        hive_home: Path | None = None,
        hive: LocalHiveStore | None = None,
        hive_id: str = "main",
        branch: str = "main",
        instance_id: str = "auto",
        session_id: str = "auto",
        role: str = "worker",
        mode: str = "isolated",
        policy: SkillPolicy | None = None,
        import_skills: bool | None = None,
        export_skills: bool | None = None,
        apply_mode: str | None = None,
        sync_mode: str | None = None,
        export_mode: str | None = None,
        owner: Any | None = None,
        initial_state: Any | None = None,
        profile_sha256: str | None = None,
        source_identity_sha256: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        owns_owner: bool | None = None,
        limits: CapacityLimits | None = None,
    ) -> "HiveField":
        field_home = Path(field_home).expanduser()
        field_home.mkdir(parents=True, exist_ok=True)
        if hive is not None and hive_home is not None:
            raise HiveRuntimeError("provide hive or hive_home, not both")
        owns_hive = hive is None
        store = hive
        if store is None:
            configured_home = hive_home or Path(
                os.environ.get("CASSI_HIVE_HOME", str(DEFAULT_HIVE_HOME))
            )
            store = LocalHiveStore(configured_home, hive_id=hive_id, branch=branch)
        elif store.hive_id != hive_id or store.branch != branch:
            raise HiveRuntimeError("provided hive store does not match requested identity")

        if owner is None:
            owner = FieldIntelligenceOwner(
                field_home, initial_state=initial_state, limits=limits
            )
            effective_owns_owner = True
        else:
            effective_owns_owner = bool(owns_owner) if owns_owner is not None else False
        adapter = adapt_owner(owner, profile_sha256=profile_sha256)
        resolved_policy = policy or SkillPolicy.for_mode(mode)
        overrides: dict[str, Any] = {}
        if import_skills is not None:
            overrides["import_enabled"] = import_skills
        if export_skills is not None:
            overrides["export_enabled"] = export_skills
        if apply_mode is not None:
            overrides["apply_mode"] = apply_mode
        if sync_mode is not None:
            overrides["sync_mode"] = sync_mode
        if export_mode is not None:
            overrides["export_mode"] = export_mode
        if overrides:
            resolved_policy = replace(resolved_policy, **overrides)
        instance = _load_or_create_instance_id(field_home, hive_id=hive_id)
        if instance_id != "auto":
            _text(instance_id, "instance_id")
            if instance != instance_id:
                _atomic_json(
                    field_home / "hive-instance.json",
                    {"hive_id": hive_id, "instance_id": instance_id, "schema": "cassifi.hive.instance.v1"},
                )
                instance = instance_id
        if session_id == "auto":
            session_id = f"{instance}:session:{uuid.uuid4().hex}"
        _text(session_id, "session_id")
        metadata_dict = {} if metadata is None else dict(metadata)
        test_name = str(metadata_dict.pop("test_name", session_id))
        arm = str(metadata_dict.pop("arm", "default"))
        seed = metadata_dict.pop("seed", None)
        configuration = metadata_dict.pop("configuration", {})
        config_digest = sha256_value(configuration)
        source_digest = source_identity_sha256 or sha256_value(
            {
                "adapter": type(adapter).__name__,
                "field_profile_sha256": adapter.field_profile_sha256,
                "runtime": RUNTIME_SCHEMA,
            }
        )
        identity = SessionIdentity(
            hive_id=hive_id,
            branch=branch,
            instance_id=instance,
            session_id=session_id,
            role=role,
            field_profile_sha256=adapter.field_profile_sha256,
            source_identity_sha256=source_digest,
            test_name=test_name,
            arm=arm,
            seed=seed,
            configuration_sha256=config_digest,
            parent_instance_id=metadata_dict.pop("parent_instance_id", None),
            metadata=metadata_dict,
        )
        connected = cls(
            owner=owner,
            adapter=adapter,
            hive=store,
            identity=identity,
            policy=resolved_policy,
            field_home=field_home,
            owns_owner=effective_owns_owner,
            owns_hive=owns_hive,
        )
        if resolved_policy.sync_mode == "on-open":
            try:
                connected.sync()
            except (HiveRuntimeError, HiveStoreError, HiveProtocolError):
                connected.close()
                raise
        return connected

    @classmethod
    def attach(cls, owner: Any, **kwargs: Any) -> "HiveField":
        """Attach an already-created owner without taking ownership by default."""

        if "field_home" not in kwargs:
            field_home = getattr(owner, "data_home", None)
            if field_home is None:
                raise HiveRuntimeError("attach requires field_home for owner-like objects without data_home")
            kwargs["field_home"] = field_home
        kwargs.setdefault("owns_owner", False)
        kwargs["owner"] = owner
        return cls.open(**kwargs)

    @classmethod
    def fork(
        cls,
        source_field_home: Path,
        field_home: Path,
        **kwargs: Any,
    ) -> "HiveField":
        """Create a new local field lineage from a verified, closed source home."""

        source = Path(source_field_home).expanduser()
        target = Path(field_home).expanduser()
        if not (source.is_dir() and (source / "field").is_dir()):
            raise HiveRuntimeError("source field home is unavailable")
        if target.exists() and any(target.iterdir()):
            raise HiveRuntimeError("fork target must not already contain field state")
        parent_instance_id: str | None = None
        source_manifest = source / "hive-instance.json"
        if source_manifest.exists():
            parent_instance_id = _read_json(source_manifest).get("instance_id")
            if parent_instance_id is not None:
                parent_instance_id = _text(parent_instance_id, "parent_instance_id")
        try:
            with FieldIntelligenceOwner(source) as source_owner:
                parent_manifest = source_owner.checkpoints.current_manifest_sha256
                parent_state = source_owner.state.state_sha256
        except Exception as exc:
            raise HiveRuntimeError("source field must be available and closed before forking") from exc
        target.mkdir(parents=True, exist_ok=True)
        ignored = shutil.ignore_patterns("OWNER.lock", "hive-instance.json", "hive-session-state.json")
        for item in source.iterdir():
            destination = target / item.name
            if item.name in {"OWNER.lock", "hive-instance.json", "hive-session-state.json"}:
                continue
            if item.is_dir():
                shutil.copytree(item, destination, ignore=ignored)
            else:
                shutil.copy2(item, destination)
        metadata = dict(kwargs.pop("metadata", {}) or {})
        metadata.setdefault("parent_instance_id", parent_instance_id)
        metadata.update(
            {
                "fork_parent_manifest_sha256": parent_manifest,
                "fork_parent_state_sha256": parent_state,
            }
        )
        field = cls.open(target, metadata=metadata, **kwargs)
        fork_document = make_document(
            FORK_SCHEMA,
            {
                "parent_instance_id": parent_instance_id,
                "parent_manifest_sha256": parent_manifest,
                "parent_state_sha256": parent_state,
                "source_field_home": str(source),
            },
        )
        field.hive.put_document(fork_document)
        return field

    def _load_state(self) -> _SessionState:
        if not self._state_path.exists():
            return _SessionState()
        value = _read_json(self._state_path)
        if value.get("schema") != SESSION_STATE_SCHEMA:
            raise HiveRuntimeError("unsupported hive session state schema")
        if value.get("instance_id") != self.identity.instance_id:
            raise HiveRuntimeError("session state belongs to another field instance")
        try:
            return _SessionState(
                common_generation=int(value.get("common_generation", 0)),
                staged_bundle_ids=tuple(value.get("staged_bundle_ids", ())),
                adopted_bundle_ids=tuple(value.get("adopted_bundle_ids", ())),
                exported_capsule_ids=tuple(value.get("exported_capsule_ids", ())),
                adoption_receipt_ids=tuple(value.get("adoption_receipt_ids", ())),
            )
        except (TypeError, ValueError) as exc:
            raise HiveRuntimeError("hive session state is malformed") from exc

    def _save_state(self) -> None:
        _atomic_json(
            self._state_path,
            self._state.as_dict(
                session_id=self.identity.session_id,
                instance_id=self.identity.instance_id,
                policy=self.policy,
            ),
        )

    def configure_exchange(
        self,
        *,
        import_skills: bool | None = None,
        export_skills: bool | None = None,
        apply_mode: str | None = None,
        sync_mode: str | None = None,
        export_mode: str | None = None,
    ) -> SkillPolicy:
        values: dict[str, Any] = {}
        if import_skills is not None:
            values["import_enabled"] = import_skills
        if export_skills is not None:
            values["export_enabled"] = export_skills
        if apply_mode is not None:
            values["apply_mode"] = apply_mode
        if sync_mode is not None:
            values["sync_mode"] = sync_mode
        if export_mode is not None:
            values["export_mode"] = export_mode
        try:
            self.policy = replace(self.policy, **values)
        except HivePolicyError as exc:
            raise HiveRuntimeError(str(exc)) from exc
        self._save_state()
        return self.policy

    def publish_experience(
        self,
        *,
        transition: Mapping[str, Any],
        task_id: str,
        context: Mapping[str, Any],
        action: Mapping[str, Any],
        prediction: Mapping[str, Any],
        outcome: Mapping[str, Any],
        candidate: ExperienceCandidate,
        evidence: ExperienceEvidence,
        transfer_visibility: str | None = None,
        maximum_admission_work: int = 4096,
        verify_checkpoints: bool = True,
        predecessor_state_sha256: str | None = None,
    ) -> ExperienceCapsule:
        if not self.policy.export_enabled:
            raise HiveRuntimeError("skill export is disabled for this session")
        try:
            capsule = capsule_from_owner_transition(
                self.adapter.owner,
                transition,
                hive_id=self.identity.hive_id,
                instance_id=self.identity.instance_id,
                role=self.identity.role,
                field_profile_sha256=self.identity.field_profile_sha256,
                common_generation=self._state.common_generation,
                task_id=task_id,
                context=context,
                action=action,
                prediction=prediction,
                outcome=outcome,
                candidate=candidate,
                evidence=evidence,
                transfer_visibility=transfer_visibility or self.policy.visibility,
                maximum_admission_work=maximum_admission_work,
                verify_checkpoints=verify_checkpoints,
                predecessor_state_sha256=predecessor_state_sha256,
            )
            self.hive.put_capsule(capsule)
        except (HiveProtocolError, HiveStoreError) as exc:
            raise HiveRuntimeError(str(exc)) from exc
        exported = list(self._state.exported_capsule_ids)
        if capsule.object_id not in exported:
            exported.append(capsule.object_id)
        self._state = replace(self._state, exported_capsule_ids=tuple(exported))
        self._save_state()
        return capsule

    def capture(self, **kwargs: Any) -> ExperienceCapsule:
        """Alias for the explicit experience publication operation."""

        return self.publish_experience(**kwargs)

    def track_experience(self, **kwargs: Any) -> _TrackedExperience:
        return _TrackedExperience(self, kwargs)

    def preview_imports(self) -> tuple[Mapping[str, Any], ...]:
        if not self.policy.import_enabled:
            return ()
        documents = self.hive.list_bundle_documents(after_generation=self._state.common_generation)
        result: list[Mapping[str, Any]] = []
        for document in documents:
            bundle = decode_bundle(document)
            if not self._bundle_allowed(bundle):
                continue
            result.append(
                {
                    "bundle_id": bundle.object_id,
                    "learned_objects": [dict(item) for item in bundle.learned_objects],
                    "predecessor_common_generation": bundle.predecessor_common_generation,
                    "resulting_common_generation": bundle.resulting_common_generation,
                    "status": bundle.status,
                }
            )
        return tuple(result)
    def preview_bundle(self, bundle_id: str) -> Mapping[str, Any]:
        try:
            bundle = decode_bundle(self.hive.get_document(_digest(bundle_id, "bundle_id")))
        except (HiveRuntimeError, HiveStoreError) as exc:
            raise HiveRuntimeError(str(exc)) from exc
        return {
            "allowed": self._bundle_allowed(bundle),
            "bundle_id": bundle.object_id,
            "compatibility": dict(bundle.compatibility),
            "current_common_generation": self._state.common_generation,
            "dependencies": list(bundle.dependencies),
            "learned_objects": [dict(item) for item in bundle.learned_objects],
            "operation_plan": [dict(item) for item in bundle.operation_plan],
            "predecessor_common_generation": bundle.predecessor_common_generation,
            "resulting_common_generation": bundle.resulting_common_generation,
            "revoked": self.hive.is_revoked(bundle.object_id),
            "source_experience_ids": list(bundle.source_experience_ids),
        }

    def sync(self) -> SyncReport:
        if not self.policy.import_enabled:
            return SyncReport()
        if self.policy.apply_mode == "never":
            documents = self.hive.list_bundle_documents(after_generation=self._state.common_generation)
            staged = list(self._state.staged_bundle_ids)
            skipped: list[str] = []
            for document in documents:
                bundle = decode_bundle(document)
                if not self._bundle_allowed(bundle):
                    skipped.append(bundle.object_id)
                    continue
                if bundle.object_id not in staged:
                    staged.append(bundle.object_id)
            self._state = replace(self._state, staged_bundle_ids=tuple(staged))
            self._save_state()
            return SyncReport(staged=tuple(staged), skipped=tuple(skipped))
        if self.policy.apply_mode == "manual":
            documents = self.hive.list_bundle_documents(after_generation=self._state.common_generation)
            staged = list(self._state.staged_bundle_ids)
            skipped: list[str] = []
            for document in documents:
                bundle = decode_bundle(document)
                if not self._bundle_allowed(bundle):
                    skipped.append(bundle.object_id)
                    continue
                if bundle.object_id not in staged:
                    staged.append(bundle.object_id)
            self._state = replace(self._state, staged_bundle_ids=tuple(staged))
            self._save_state()
            return SyncReport(staged=tuple(staged), skipped=tuple(skipped))
        return self._apply_available(
            self.hive.list_bundle_documents(after_generation=self._state.common_generation)
        )

    def sync_staged(self) -> SyncReport:
        documents: list[Mapping[str, Any]] = []
        for bundle_id in self._state.staged_bundle_ids:
            documents.append(self.hive.get_document(bundle_id))
        return self._apply_available(documents)

    def adopt(self, *, bundle_ids: Sequence[str] | None = None) -> SyncReport:
        if not self.policy.import_enabled:
            raise HiveRuntimeError("skill import is disabled for this session")
        selected = self._state.staged_bundle_ids if bundle_ids is None else tuple(bundle_ids)
        documents = [self.hive.get_document(_digest(bundle_id, "bundle_id")) for bundle_id in selected]
        return self._apply_available(documents)
    def adopt_and_record_outcome(
        self,
        bundle_id: str,
        *,
        assessment_id: str,
    ) -> tuple[SyncReport, OutcomeEvidence]:
        """Apply a bundle and consume immutable execution-backed assessment."""

        _digest(assessment_id, "assessment_id")
        try:
            assessment_document = self.hive.get_document(assessment_id)
            assessment = ExecutionAssessment.from_document(
                assessment_document
            )
        except (CollectiveHiveError, HiveStoreError, ValueError) as exc:
            raise HiveRuntimeError(
                "execution assessment is unavailable or invalid"
            ) from exc
        if assessment.object_id != assessment_id:
            raise HiveRuntimeError(
                "execution assessment identity does not match its content"
            )
        if (
            assessment.bundle_id != bundle_id
            or assessment.recipient_instance_id
            != self.identity.instance_id
        ):
            raise HiveRuntimeError(
                "execution assessment does not bind this member and bundle"
            )
        receipt_document: Mapping[str, Any] | None = None
        for document in reversed(
            self.hive.list_adoptions(
                instance_id=self.identity.instance_id
            )
        ):
            if document.get("object_id") == assessment.adoption_receipt_id:
                receipt_document = document
                break
        if receipt_document is None:
            raise HiveRuntimeError(
                "execution assessment adoption receipt is unavailable"
            )
        try:
            receipt = AdoptionReceipt(
                **receipt_document.get("content", {})
            )
        except (HiveProtocolError, TypeError, ValueError) as exc:
            raise HiveRuntimeError(
                "execution assessment adoption receipt is invalid"
            ) from exc
        if (
            receipt.object_id != assessment.adoption_receipt_id
            or receipt.bundle_id != bundle_id
            or receipt.recipient_instance_id
            != self.identity.instance_id
        ):
            raise HiveRuntimeError(
                "execution assessment does not bind this adoption"
            )
        if receipt.status not in {
            "accepted",
            "accepted-with-local-guard",
            "replayed",
        }:
            raise HiveRuntimeError(
                "completed adoption receipt is not admissible"
            )
        if bundle_id not in self._state.adopted_bundle_ids:
            raise HiveRuntimeError(
                "assessed bundle is absent from the member field"
            )
        report = (
            SyncReport(replayed=(bundle_id,))
            if receipt.status == "replayed"
            else SyncReport(applied=(bundle_id,))
        )
        for trace_id in assessment.trace_document_ids:
            try:
                self.hive.get_document(trace_id)
            except HiveStoreError as exc:
                raise HiveRuntimeError(
                    "execution assessment trace evidence is unavailable"
                ) from exc
        outcome = OutcomeEvidence(
            bundle_id=bundle_id,
            recipient_instance_id=self.identity.instance_id,
            adoption_receipt_id=receipt.object_id,
            protocol_sha256=assessment.protocol_sha256,
            metrics=assessment.metrics,
            held_out=assessment.held_out,
            failure_modes=assessment.failure_modes,
            observed_ns=assessment.observed_ns,
            valid_until_ns=assessment.valid_until_ns,
            execution_assessment_id=assessment.object_id,
            trace_document_ids=assessment.trace_document_ids,
            evaluator_id=assessment.evaluator_id,
            evaluator_version=assessment.evaluator_version,
            scoring_rule=assessment.scoring_rule,
        )
        self.collective.record_outcome(outcome)
        return report, outcome

    def _apply_available(self, documents: Sequence[Mapping[str, Any]]) -> SyncReport:
        staged: list[str] = []
        applied: list[str] = []
        replayed: list[str] = []
        skipped: list[str] = []
        blocked: list[str] = []
        errors: list[Mapping[str, Any]] = []
        for document in documents:
            try:
                bundle = decode_bundle(document)
            except HiveStoreError as exc:
                errors.append({"code": "INVALID_BUNDLE", "error": str(exc)})
                break
            if self.hive.is_revoked(bundle.object_id):
                blocked.append(bundle.object_id)
                errors.append(
                    {
                        "bundle_id": bundle.object_id,
                        "code": "REVOKED_BUNDLE",
                        "error": "bundle has been revoked",
                    }
                )
                break
            if not self._bundle_allowed(bundle):
                skipped.append(bundle.object_id)
                continue
            if bundle.object_id in self._state.adopted_bundle_ids:
                replayed.append(bundle.object_id)
                continue
            if bundle.predecessor_common_generation != self._state.common_generation:
                blocked.append(bundle.object_id)
                break
            try:
                receipt = self.adapter.apply_bundle(
                    bundle,
                    recipient_instance_id=self.identity.instance_id,
                    current_common_generation=self._state.common_generation,
                    field_effect_confirmed=True,
                )
                self.hive.record_adoption(receipt, session_id=self.identity.session_id)
            except (HiveAdapterError, HiveProtocolError, HiveStoreError) as exc:
                errors.append({"bundle_id": bundle.object_id, "code": "ADOPTION_FAILED", "error": str(exc)})
                blocked.append(bundle.object_id)
                break
            if receipt.status in {"accepted", "accepted-with-local-guard"}:
                applied.append(bundle.object_id)
                self._state = replace(
                    self._state,
                    common_generation=bundle.resulting_common_generation,
                    adopted_bundle_ids=_append_unique(self._state.adopted_bundle_ids, bundle.object_id),
                    adoption_receipt_ids=_append_unique(self._state.adoption_receipt_ids, receipt.object_id),
                )
            elif receipt.status == "replayed":
                replayed.append(bundle.object_id)
                self._state = replace(
                    self._state,
                    common_generation=bundle.resulting_common_generation,
                    adopted_bundle_ids=_append_unique(self._state.adopted_bundle_ids, bundle.object_id),
                    adoption_receipt_ids=_append_unique(self._state.adoption_receipt_ids, receipt.object_id),
                )
            else:
                blocked.append(bundle.object_id)
                self._state = replace(
                    self._state,
                    adoption_receipt_ids=_append_unique(self._state.adoption_receipt_ids, receipt.object_id),
                )
                self._save_state()
                break
            staged = [item for item in self._state.staged_bundle_ids if item != bundle.object_id]
            self._state = replace(self._state, staged_bundle_ids=tuple(staged))
            self._save_state()
        return SyncReport(
            staged=tuple(staged),
            applied=tuple(applied),
            replayed=tuple(replayed),
            skipped=tuple(skipped),
            blocked=tuple(blocked),
            errors=tuple(errors),
        )
    def _bundle_allowed(self, bundle: KnowledgeBundle) -> bool:
        if bundle.hive_id != self.identity.hive_id:
            return False
        compatibility = bundle.compatibility
        profile_match = (
            compatibility.get("field_profile_sha256")
            == self.identity.field_profile_sha256
        )
        portable_match = (
            compatibility.get("field_profile_sha256") == PORTABLE_PROFILE_SHA256
            and compatibility.get("portable_transfer_schema") == PORTABLE_TRANSFER_SCHEMA
            and compatibility.get("atlas_schema") == self.identity.atlas_schema
            and len(bundle.learned_objects) == 1
            and bundle.learned_objects[0].get("kind") == "field-program"
            and len(bundle.operation_plan) == 1
            and bundle.operation_plan[0].get("operation")
            in {"configure-program", "promote-program"}
            and self.adapter.supports_portable_transfer(PORTABLE_TRANSFER_SURFACE)
        )
        if not profile_match and not portable_match:
            return False
        if compatibility.get("atlas_schema") != self.identity.atlas_schema:
            return False
        if self.policy.allowed_kinds:
            kinds = {str(item.get("kind")) for item in bundle.learned_objects}
            if not kinds.issubset(set(self.policy.allowed_kinds)):
                return False
        if self.policy.allowed_domains:
            domain = bundle.compatibility.get("domain")
            if domain is not None and domain not in self.policy.allowed_domains:
                return False
        return True

    def configure_policy(self, policy: SkillPolicy) -> SkillPolicy:
        if not isinstance(policy, SkillPolicy):
            raise HiveRuntimeError("policy must be a SkillPolicy")
        self.policy = policy
        self._save_state()
        return policy

    def status(self) -> Mapping[str, Any]:
        store_status = dict(self.hive.status())
        return {
            "adopted_bundle_ids": list(self._state.adopted_bundle_ids),
            "adoption_receipt_ids": list(self._state.adoption_receipt_ids),
            "common_generation": self._state.common_generation,
            "exported_capsule_ids": list(self._state.exported_capsule_ids),
            "field_home": str(self.field_home),
            "field_profile_sha256": self.identity.field_profile_sha256,
            "hive": store_status,
            "identity": self.identity.as_dict(),
            "manifest_sha256": self.adapter.manifest_sha256,
            "pending_bundle_ids": list(self._state.staged_bundle_ids),
            "policy": self.policy.as_dict(),
            "state_sha256": self.adapter.state_sha256,
            "status_schema": RUNTIME_SCHEMA,
        }

    def timeline(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(
            {
                "bundle_id": document["content"].get("bundle_id"),
                "object_id": document["object_id"],
                "schema": document["schema"],
            }
            for document in self.hive.list_adoptions(instance_id=self.identity.instance_id)
        )

    def close(self) -> None:
        errors: list[BaseException] = []
        try:
            self.hive.update_session(self.identity.session_id, "closed")
            self._save_state()
        except BaseException as exc:
            errors.append(exc)
        if self._owns_owner:
            try:
                self.adapter.close()
            except BaseException as exc:
                errors.append(exc)
        if self._owns_hive:
            try:
                self.hive.close()
            except BaseException as exc:
                errors.append(exc)
        if errors:
            raise HiveRuntimeError("hive session close failed") from errors[0]

    def __enter__(self) -> "HiveField":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def __getattr__(self, name: str) -> Any:
        facade = self.__dict__.get("_owner_facade")
        if facade is not None:
            return getattr(facade, name)
        raise AttributeError(name)



def _append_unique(values: Sequence[str], value: str) -> tuple[str, ...]:
    result = list(values)
    if value not in result:
        result.append(value)
    return tuple(result)


def _load_or_create_instance_id(field_home: Path, *, hive_id: str) -> str:
    path = field_home / "hive-instance.json"
    if path.exists():
        value = _read_json(path)
        if value.get("schema") != "cassifi.hive.instance.v1" or value.get("hive_id") != hive_id:
            raise HiveRuntimeError("field instance manifest is incompatible with the requested hive")
        return _text(value.get("instance_id"), "instance_id")
    instance_id = f"instance-{uuid.uuid4().hex}"
    _atomic_json(
        path,
        {"hive_id": hive_id, "instance_id": instance_id, "schema": "cassifi.hive.instance.v1"},
    )
    return instance_id


__all__ = [
    "HiveField",
    "HiveRuntimeError",
    "RUNTIME_SCHEMA",
    "SESSION_STATE_SCHEMA",
    "SessionIdentity",
    "SkillController",
    "SyncReport",
]
