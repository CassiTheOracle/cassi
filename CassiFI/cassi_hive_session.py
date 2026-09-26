"""Canonical shared-hive session constructors for Cassi field programs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from cassi_hive_policy import SkillPolicy
from cassi_hive_runtime import HiveField


def open_field_session(
    data_home: Path,
    *,
    role: str = "worker",
    mode: str = "scout",
    instance_id: str = "auto",
    session_id: str = "auto",
    hive_id: str = "main",
    branch: str = "main",
    hive_home: Path | None = None,
    policy: SkillPolicy | None = None,
    metadata: Mapping[str, Any] | None = None,
    initial_state: Any | None = None,
    profile_sha256: str | None = None,
    limits: Any | None = None,
    **policy_overrides: Any,
) -> HiveField:
    """Open a field owner on the canonical shared hive boundary.

    Programs should use this instead of constructing ``FieldIntelligenceOwner``
    directly.  The returned ``HiveField`` owns the hive session and, by default,
    exports committed transitions without enabling bundle application.
    """

    return HiveField.open(
        Path(data_home),
        hive_home=hive_home,
        hive_id=hive_id,
        branch=branch,
        instance_id=instance_id,
        session_id=session_id,
        role=role,
        mode=mode,
        policy=policy,
        metadata=metadata,
        initial_state=initial_state,
        profile_sha256=profile_sha256,
        limits=limits,
        **policy_overrides,
    )


def attach_field_session(
    owner: Any,
    *,
    data_home: Path,
    role: str = "worker",
    mode: str = "scout",
    instance_id: str = "auto",
    session_id: str = "auto",
    hive_id: str = "main",
    branch: str = "main",
    hive_home: Path | None = None,
    policy: SkillPolicy | None = None,
    metadata: Mapping[str, Any] | None = None,
    **policy_overrides: Any,
) -> HiveField:
    """Attach an existing field owner to the canonical shared hive."""

    return HiveField.attach(
        owner,
        field_home=Path(data_home),
        hive_home=hive_home,
        hive_id=hive_id,
        branch=branch,
        instance_id=instance_id,
        session_id=session_id,
        role=role,
        mode=mode,
        policy=policy,
        metadata=metadata,
        **policy_overrides,
    )


__all__ = ["attach_field_session", "open_field_session"]
