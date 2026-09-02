from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Literal

from cassi_universal_data import JournalReference


TaskSplit = Literal["training", "holdout"]
TaskStatus = Literal["selected", "ambiguous", "exhausted"]


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 256:
        raise ValueError(f"{name} must be nonempty and at most 256 UTF-8 bytes")


def _span(value: bytes, name: str) -> None:
    if not isinstance(value, bytes) or not value:
        raise ValueError(f"{name} must be a nonempty byte span")


def _digest(value: str, name: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class TaskCorpusEpisode:
    source_id: str
    prompt: bytes
    continuation: bytes
    payload_sha256: str

    def __post_init__(self) -> None:
        _text(self.source_id, "source_id")
        _span(self.prompt, "prompt")
        _span(self.continuation, "continuation")
        _digest(self.payload_sha256, "payload_sha256")
        if hashlib.sha256(self.prompt + self.continuation).hexdigest() != self.payload_sha256:
            raise ValueError("payload_sha256 does not match prompt plus continuation")


@dataclass(frozen=True, slots=True)
class TaskObservation:
    episode_id: str
    source_id: str
    split: TaskSplit
    codec_id: str
    prompt: bytes
    packet_sha256: str
    view_sha256: str
    reference: JournalReference

    def __post_init__(self) -> None:
        _text(self.episode_id, "episode_id")
        _text(self.source_id, "source_id")
        _text(self.codec_id, "codec_id")
        if self.split not in ("training", "holdout"):
            raise ValueError("split must be training or holdout")
        _span(self.prompt, "prompt")
        _digest(self.packet_sha256, "packet_sha256")
        _digest(self.view_sha256, "view_sha256")
        if not isinstance(self.reference, JournalReference):
            raise ValueError("reference must be a JournalReference")
        if self.reference.packet_sha256 != self.packet_sha256:
            raise ValueError("reference packet digest does not match observation")


@dataclass(frozen=True, slots=True)
class TaskEpisode:
    episode_id: str
    family: str
    split: TaskSplit
    source_id: str
    codec_id: str
    packet_sha256: str
    view_sha256: str
    reference: JournalReference
    prompt: bytes
    target: bytes

    def __post_init__(self) -> None:
        _text(self.episode_id, "episode_id")
        _text(self.family, "family")
        _text(self.source_id, "source_id")
        _text(self.codec_id, "codec_id")
        if self.split not in ("training", "holdout"):
            raise ValueError("split must be training or holdout")
        _digest(self.packet_sha256, "packet_sha256")
        _digest(self.view_sha256, "view_sha256")
        if not isinstance(self.reference, JournalReference):
            raise ValueError("reference must be a JournalReference")
        if self.reference.packet_sha256 != self.packet_sha256:
            raise ValueError("reference packet digest does not match task episode")
        _span(self.prompt, "prompt")
        _span(self.target, "target")


@dataclass(frozen=True, slots=True)
class TaskReceipt:
    family: str
    status: TaskStatus
    program_sha256: str | None
    tokens: tuple[str, ...]
    exact: int
    total: int
    accuracy: float

    def __post_init__(self) -> None:
        _text(self.family, "family")
        if self.status not in ("selected", "ambiguous", "exhausted"):
            raise ValueError("task receipt status is invalid")
        if (
            isinstance(self.exact, bool)
            or not isinstance(self.exact, int)
            or isinstance(self.total, bool)
            or not isinstance(self.total, int)
            or self.total < 1
            or not 0 <= self.exact <= self.total
            or not isinstance(self.accuracy, float)
            or not math.isfinite(self.accuracy)
            or self.accuracy != self.exact / self.total
        ):
            raise ValueError("task receipt counts and accuracy are inconsistent")
        if self.status == "selected":
            if self.program_sha256 is None or not self.tokens:
                raise ValueError("selected task receipt lacks a program identity")
            _digest(self.program_sha256, "program_sha256")
        elif self.program_sha256 is not None or self.tokens:
            raise ValueError("unsettled task receipt cannot identify a program")
