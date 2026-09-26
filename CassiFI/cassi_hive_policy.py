"""User-facing policy for Cassi Hive skill exchange.

The policy controls the control-plane flow around a local field owner.  It does
not introduce adaptive state: the owner field remains the only learned state.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


POLICY_SCHEMA = "cassifi.hive.skill-policy.v1"
_MODES = frozenset({"isolated", "scout", "member", "reviewer", "leader"})
_APPLY_MODES = frozenset({"never", "manual", "verified"})
_SYNC_MODES = frozenset({"manual", "on-open", "on-close", "boundary", "watch"})
_EXPORT_MODES = frozenset({"explicit", "on-close"})
_VISIBILITIES = frozenset({"public", "provenance-only"})


class HivePolicyError(ValueError):
    """Raised when a hive policy is malformed or internally inconsistent."""


def _bounded_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or any(ord(char) < 32 for char in value):
        raise HivePolicyError(f"{label} must be bounded nonempty text")
    if len(value.encode("utf-8")) > 512:
        raise HivePolicyError(f"{label} is too large")
    return value


def _tuple_text(values: Sequence[str], label: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise HivePolicyError(f"{label} must be a sequence")
    result = tuple(_bounded_text(value, label) for value in values)
    if len(result) != len(set(result)):
        raise HivePolicyError(f"{label} must not contain duplicates")
    return result


@dataclass(frozen=True, slots=True)
class SkillPolicy:
    """Explicit exchange policy for one connected field session.

    ``import_enabled`` only permits bundles to enter the session's staged
    inbox.  ``apply_mode`` controls whether those bundles can mutate the local
    owner.  This separation prevents a test from changing its field merely by
    discovering that a hive bundle exists.
    """

    import_enabled: bool = False
    export_enabled: bool = True
    review_enabled: bool = False
    apply_mode: str = "never"
    sync_mode: str = "manual"
    export_mode: str = "explicit"
    allowed_kinds: tuple[str, ...] = ()
    allowed_domains: tuple[str, ...] = ()
    minimum_support_reviews: int = 2
    allow_local_guard: bool = True
    visibility: str = "provenance-only"
    fail_if_unavailable: bool = False

    def __post_init__(self) -> None:
        for name in ("import_enabled", "export_enabled", "review_enabled", "allow_local_guard", "fail_if_unavailable"):
            if not isinstance(getattr(self, name), bool):
                raise HivePolicyError(f"{name} must be Boolean")
        if self.apply_mode not in _APPLY_MODES:
            raise HivePolicyError(f"apply_mode must be one of {sorted(_APPLY_MODES)}")
        if self.sync_mode not in _SYNC_MODES:
            raise HivePolicyError(f"sync_mode must be one of {sorted(_SYNC_MODES)}")
        if self.export_mode not in _EXPORT_MODES:
            raise HivePolicyError(f"export_mode must be one of {sorted(_EXPORT_MODES)}")
        object.__setattr__(self, "allowed_kinds", _tuple_text(self.allowed_kinds, "allowed_kinds"))
        object.__setattr__(self, "allowed_domains", _tuple_text(self.allowed_domains, "allowed_domains"))
        if isinstance(self.minimum_support_reviews, bool) or not isinstance(self.minimum_support_reviews, int):
            raise HivePolicyError("minimum_support_reviews must be an integer")
        if self.minimum_support_reviews < 1:
            raise HivePolicyError("minimum_support_reviews must be positive")
        if self.visibility not in _VISIBILITIES:
            raise HivePolicyError(f"visibility must be one of {sorted(_VISIBILITIES)}")
        if not self.import_enabled and self.apply_mode != "never":
            raise HivePolicyError("apply_mode requires import_enabled")
        if self.apply_mode == "never" and self.sync_mode == "watch":
            raise HivePolicyError("watch sync requires an applying policy")

    @classmethod
    def for_mode(cls, mode: str, **overrides: Any) -> "SkillPolicy":
        """Return a safe named policy, with explicit keyword overrides."""

        _bounded_text(mode, "mode")
        if mode not in _MODES:
            raise HivePolicyError(f"mode must be one of {sorted(_MODES)}")
        values: dict[str, Any] = {
            "import_enabled": False,
            "export_enabled": True,
            "review_enabled": False,
            "apply_mode": "never",
            "sync_mode": "manual",
            "export_mode": "explicit",
        }
        if mode == "scout":
            values.update(export_enabled=True, export_mode="on-close")
        elif mode == "member":
            values.update(
                import_enabled=True,
                export_enabled=True,
                apply_mode="verified",
                sync_mode="on-open",
                export_mode="on-close",
            )
        elif mode == "reviewer":
            values.update(import_enabled=True, review_enabled=True, apply_mode="never")
        elif mode == "leader":
            values.update(
                import_enabled=True,
                export_enabled=True,
                review_enabled=True,
                apply_mode="manual",
                sync_mode="manual",
                export_mode="on-close",
            )
        values.update(overrides)
        return cls(**values)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "SkillPolicy":
        """Load an explicit policy from ``CASSI_HIVE_*`` environment values."""

        source = os.environ if env is None else env
        mode = source.get("CASSI_HIVE_MODE", "isolated")
        values: dict[str, Any] = {}
        if "CASSI_HIVE_IMPORT_SKILLS" in source:
            values["import_enabled"] = _env_bool(source["CASSI_HIVE_IMPORT_SKILLS"], "CASSI_HIVE_IMPORT_SKILLS")
        if "CASSI_HIVE_EXPORT_SKILLS" in source:
            values["export_enabled"] = _env_bool(source["CASSI_HIVE_EXPORT_SKILLS"], "CASSI_HIVE_EXPORT_SKILLS")
        for key, field in (
            ("CASSI_HIVE_APPLY_MODE", "apply_mode"),
            ("CASSI_HIVE_SYNC_MODE", "sync_mode"),
            ("CASSI_HIVE_EXPORT_MODE", "export_mode"),
            ("CASSI_HIVE_VISIBILITY", "visibility"),
        ):
            if key in source:
                values[field] = source[key]
        return cls.for_mode(mode, **values)

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "allowed_domains": list(self.allowed_domains),
            "allowed_kinds": list(self.allowed_kinds),
            "allow_local_guard": self.allow_local_guard,
            "apply_mode": self.apply_mode,
            "export_enabled": self.export_enabled,
            "export_mode": self.export_mode,
            "fail_if_unavailable": self.fail_if_unavailable,
            "import_enabled": self.import_enabled,
            "minimum_support_reviews": self.minimum_support_reviews,
            "review_enabled": self.review_enabled,
            "schema": POLICY_SCHEMA,
            "sync_mode": self.sync_mode,
            "visibility": self.visibility,
        }


def _env_bool(value: str, label: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise HivePolicyError(f"{label} must be a Boolean environment value")


__all__ = ["POLICY_SCHEMA", "HivePolicyError", "SkillPolicy"]
