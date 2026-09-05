"""Strict zero-runtime-side-effect adapter from an L18 decode record to the organism teacher weave.

This module is a pure boundary: it converts a validated
:class:`~l18_generated_token_trajectory.DecodeRecord` into a
:class:`~cassi_organism_law.CassiAllLayerTeacherWeave` without instantiating or
loading the L18 runtime, without mutating the record, and without retaining any
reference to the record's backing arrays. All copies, stop-gradient semantics,
finite checks, and CPU-float32 ownership are delegated to
``CassiAllLayerTeacherWeave.from_layers``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import torch
from torch import Tensor

from cassi_organism_law import CassiAllLayerTeacherWeave, CassiOrganismLawError
from l18_generated_token_trajectory import DecodeRecord, TRUNK_LAYER_COUNT

FIELD_TRUNK_ROLE: Final[str] = "field_trunk"

__all__ = [
    "CassiTeacherWeaveError",
    "runtime_artifact_sha256",
    "teacher_weave_from_decode",
]


class CassiTeacherWeaveError(ValueError):
    """A checked failure adapting a DecodeRecord into a CassiAllLayerTeacherWeave."""


def teacher_weave_from_decode(
    record: DecodeRecord,
    *,
    source_model_sha256: str,
    source_runtime_sha256: str,
    token_index: int | None = None,
) -> CassiAllLayerTeacherWeave:
    """Adapt one validated DecodeRecord into a frozen all-layer teacher weave.

    The record's trunk captures are consumed in true ascending layer order
    0..63 exactly once; the separate layer-64 head-output reference is never
    part of the weave.  ``token_index`` is only for an initial decode, whose
    trajectory record intentionally uses ``-1`` before a source token index is
    assigned.  It is otherwise required to equal the record's own index.
    Copies, stop-gradient, finite checks, and CPU-float32 ownership are
    delegated to :func:`CassiAllLayerTeacherWeave.from_layers`.
    """
    if not isinstance(record, DecodeRecord):
        raise CassiTeacherWeaveError(
            f"record must be a DecodeRecord, got {type(record).__name__}"
        )
    resolved_token_index = record.token_index if token_index is None else token_index
    if (
        isinstance(resolved_token_index, bool)
        or not isinstance(resolved_token_index, int)
        or resolved_token_index < 0
    ):
        raise CassiTeacherWeaveError("teacher token_index must be a nonnegative integer")
    if token_index is not None and record.token_index >= 0 and token_index != record.token_index:
        raise CassiTeacherWeaveError(
            "token_index override is permitted only for an initial trajectory decode"
        )
    trunk = record.trunk
    if len(trunk) != TRUNK_LAYER_COUNT:
        raise CassiTeacherWeaveError(
            f"trunk must contain {TRUNK_LAYER_COUNT} captures, got {len(trunk)}"
        )
    layers: list[Tensor] = []
    for expected_index, capture in enumerate(trunk):
        if capture.layer_index != expected_index:
            raise CassiTeacherWeaveError(
                f"trunk capture {expected_index} reports layer_index "
                f"{capture.layer_index}; expected true ascending order "
                f"0..{TRUNK_LAYER_COUNT - 1}"
            )
        if capture.role != FIELD_TRUNK_ROLE:
            raise CassiTeacherWeaveError(
                f"trunk capture {expected_index} has role {capture.role!r}; "
                f"expected {FIELD_TRUNK_ROLE!r}"
            )
        layers.append(torch.as_tensor(capture.values))
    try:
        return CassiAllLayerTeacherWeave.from_layers(
            layers,
            source_model_sha256=source_model_sha256,
            source_runtime_sha256=source_runtime_sha256,
            token_index=resolved_token_index,
        )
    except CassiOrganismLawError as error:
        raise CassiTeacherWeaveError(
            f"teacher weave construction failed: {error}"
        ) from error


def runtime_artifact_sha256(paths: Sequence[Path | str]) -> str:
    """Deterministic SHA-256 over an ordered list of existing regular files.

    The digest binds each portable filename, byte length, and byte contents, in
    order. The list must be nonempty; every path must resolve to an existing
    regular file; duplicates are rejected.
    """
    hasher = hashlib.sha256()
    seen: set[Path] = set()
    count = 0
    for raw in paths:
        path = Path(raw).resolve()
        if path in seen:
            raise CassiTeacherWeaveError(f"duplicate runtime artifact: {path}")
        seen.add(path)
        if not path.is_file():
            raise CassiTeacherWeaveError(
                f"runtime artifact must be an existing regular file: {path}"
            )
        before = path.stat()
        hasher.update(path.name.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(before.st_size.to_bytes(8, "little"))
        hasher.update(b"\x00")
        read_size = 0
        with path.open("rb") as handle:
            while chunk := handle.read(1 << 20):
                hasher.update(chunk)
                read_size += len(chunk)
        after = path.stat()
        if read_size != before.st_size or (after.st_size, after.st_mtime_ns) != (
            before.st_size,
            before.st_mtime_ns,
        ):
            raise CassiTeacherWeaveError(
                f"runtime artifact changed while hashing: {path}"
            )
        count += 1
    if count == 0:
        raise CassiTeacherWeaveError("runtime artifact list must be nonempty")
    return hasher.hexdigest()
