"""Adapters between Cassi Hive and field-owned session implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from cassi_field_atlas import ATLAS_SCHEMA, sha256_value
from cassi_field_hive import AdoptionReceipt, KnowledgeBundle, apply_bundle_to_owner


FIELD_PROFILE_SCHEMA = "cassifi.hive.field-profile.v1"
PORTABLE_TRANSFER_SURFACE = "field-program.v1"
DEFAULT_FIELD_PROFILE_SHA256 = sha256_value(
    {
        "atlas_schema": ATLAS_SCHEMA,
        "candidate_surface": "field-native-semantic-v1",
        "checkpoint_schema": "cassifi.field-atlas-checkpoint.v2",
        "portable_transfer_surface": PORTABLE_TRANSFER_SURFACE,
        "schema": FIELD_PROFILE_SCHEMA,
    }
)


class HiveAdapterError(RuntimeError):
    """Raised when a field adapter cannot expose the required owner boundary."""


@runtime_checkable
class FieldAdapter(Protocol):
    owner: Any

    @property
    def field_profile_sha256(self) -> str: ...

    @property
    def atlas_schema(self) -> str: ...

    @property
    def state_sha256(self) -> str: ...

    @property
    def manifest_sha256(self) -> str: ...
    def supports_portable_transfer(self, surface: str) -> bool: ...

    def available_object_ids(self) -> tuple[str, ...]: ...

    def apply_bundle(
        self,
        bundle: KnowledgeBundle,
        *,
        recipient_instance_id: str,
        current_common_generation: int,
        field_effect_confirmed: bool,
        behavioral_delta: Mapping[str, Any] | None = None,
    ) -> AdoptionReceipt: ...


@dataclass(slots=True)
class NativeOwnerAdapter:
    """Adapter for the canonical ``FieldIntelligenceOwner`` boundary."""

    owner: Any
    profile_sha256: str = DEFAULT_FIELD_PROFILE_SHA256

    def __post_init__(self) -> None:
        if not hasattr(self.owner, "state") or not hasattr(self.owner, "checkpoints"):
            raise HiveAdapterError("native owner must expose state and checkpoints")
        if not isinstance(self.profile_sha256, str) or len(self.profile_sha256) != 64:
            raise HiveAdapterError("profile_sha256 must be a SHA-256 digest")

    @property
    def field_profile_sha256(self) -> str:
        return self.profile_sha256

    @property
    def atlas_schema(self) -> str:
        return ATLAS_SCHEMA

    @property
    def state_sha256(self) -> str:
        value = getattr(self.owner.state, "state_sha256", None)
        if not isinstance(value, str):
            raise HiveAdapterError("owner state does not expose state_sha256")
        return value

    @property
    def manifest_sha256(self) -> str:
        value = getattr(self.owner.checkpoints, "current_manifest_sha256", None)
        if not isinstance(value, str):
            raise HiveAdapterError("owner checkpoints do not expose current_manifest_sha256")
        return value

    def available_object_ids(self) -> tuple[str, ...]:
        """Return declared local dependencies without inventing adaptive state."""

        found: set[str] = set()
        state = self.owner.state
        for attribute in (
            "variables",
            "charts",
            "programs",
            "computers",
            "temporal_memories",
            "resonant_memories",
        ):
            rows = getattr(state, attribute, ())
            if isinstance(rows, Mapping):
                rows = rows.values()
            if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
                continue
            for row in rows:
                for name in ("variable_id", "chart_id", "program_id", "computer_id", "memory_id"):
                    value = getattr(row, name, None)
                    if isinstance(value, str):
                        found.add(value)
                as_dict = getattr(row, "as_dict", None)
                if callable(as_dict):
                    try:
                        found.add(sha256_value(as_dict()))
                    except (TypeError, ValueError):
                        pass
        return tuple(sorted(found))
    def supports_portable_transfer(self, surface: str) -> bool:
        return surface == PORTABLE_TRANSFER_SURFACE and callable(
            getattr(self.owner, "configure_program", None)
        )

    def apply_bundle(
        self,
        bundle: KnowledgeBundle,
        *,
        recipient_instance_id: str,
        current_common_generation: int,
        field_effect_confirmed: bool,
        behavioral_delta: Mapping[str, Any] | None = None,
    ) -> AdoptionReceipt:
        return apply_bundle_to_owner(
            self.owner,
            bundle,
            recipient_instance_id=recipient_instance_id,
            field_profile_sha256=self.field_profile_sha256,
            current_common_generation=current_common_generation,
            available_object_ids=self.available_object_ids(),
            behavioral_delta=behavioral_delta,
            field_effect_confirmed=field_effect_confirmed,
        )

    def close(self) -> None:
        close = getattr(self.owner, "close", None)
        if callable(close):
            close()


class ReadOnlyAdapter:
    """Adapter for sessions that can publish evidence but cannot adopt skills."""

    def __init__(self, owner: Any, *, profile_sha256: str = DEFAULT_FIELD_PROFILE_SHA256) -> None:
        self.owner = owner
        self.profile_sha256 = profile_sha256

    @property
    def field_profile_sha256(self) -> str:
        return self.profile_sha256

    @property
    def atlas_schema(self) -> str:
        return ATLAS_SCHEMA

    @property
    def state_sha256(self) -> str:
        return sha256_value({"adapter": "read-only", "owner": type(self.owner).__name__})

    @property
    def manifest_sha256(self) -> str:
        return self.state_sha256

    def available_object_ids(self) -> tuple[str, ...]:
        return ()
    def supports_portable_transfer(self, surface: str) -> bool:
        del surface
        return False

    def apply_bundle(self, *args: Any, **kwargs: Any) -> AdoptionReceipt:
        del args, kwargs
        raise HiveAdapterError("read-only sessions cannot adopt hive bundles")

    def close(self) -> None:
        return None


def adapt_owner(owner: Any, *, profile_sha256: str | None = None) -> FieldAdapter:
    """Select the native adapter, including wrappers exposing ``.owner``."""

    native = owner
    if not hasattr(native, "state") or not hasattr(native, "checkpoints"):
        nested = getattr(native, "owner", None)
        if nested is not None and hasattr(nested, "state") and hasattr(nested, "checkpoints"):
            native = nested
    if profile_sha256 is None:
        profile_sha256 = getattr(
            owner,
            "hive_field_profile_sha256",
            getattr(native, "hive_field_profile_sha256", DEFAULT_FIELD_PROFILE_SHA256),
        )
    return NativeOwnerAdapter(native, profile_sha256=profile_sha256)


__all__ = [
    "DEFAULT_FIELD_PROFILE_SHA256",
    "FIELD_PROFILE_SCHEMA",
    "PORTABLE_TRANSFER_SURFACE",
    "FieldAdapter",
    "HiveAdapterError",
    "NativeOwnerAdapter",
    "ReadOnlyAdapter",
    "adapt_owner",
]
