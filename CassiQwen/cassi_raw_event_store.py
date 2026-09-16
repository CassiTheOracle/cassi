"""Crash-visible exact-once persistence for the raw-event Qi learner."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

from cassi_raw_event_field import (
    AcquisitionProfile,
    CheckpointError,
    EventError,
    RawEvent,
    RawEventLearner,
)


_STORE_SCHEMA = "cassi.raw-event-store.v1"
_GENERATION_SCHEMA = "cassi.raw-event-store-generation.v1"
_MAX_EVENTS = 4096
_MAX_GENERATIONS = 8192
_MAX_JOURNAL_BYTES = 8 << 20


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _journal_bytes(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(_canonical(row) + b"\n" for row in rows)


def _parse_journal(payload: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(payload.splitlines(), start=1):
        if not line:
            continue
        try:
            row = json.loads(line.decode("utf-8"))
        except Exception as exc:
            raise CheckpointError(
                f"journal line {line_number} is invalid JSON: {exc}"
            ) from exc
        if not isinstance(row, dict):
            raise CheckpointError(f"journal line {line_number} is not an object")
        if set(row) != {"event", "learn", "promote", "revoked"}:
            raise CheckpointError(f"journal line {line_number} has unknown fields")
        RawEvent.from_dict(row["event"])
        if not isinstance(row["learn"], bool) or not isinstance(row["promote"], bool):
            raise CheckpointError(f"journal line {line_number} flags are invalid")
        if not isinstance(row["revoked"], bool):
            raise CheckpointError(f"journal line {line_number} revocation is invalid")
        rows.append(row)
    return rows


class RawEventStore:
    """Single-writer immutable-generation store.

    Every successful admission writes a new immutable generation containing
    the complete exact event journal, field checkpoint, and a hash-bound
    manifest, then atomically swaps ``CURRENT``.  Ordinary admissions only
    advance the live learner.  Episode revocation is explicitly exceptional:
    it rebuilds the field from surviving reset-bounded episodes because the
    nonlinear Qi evolution cannot be subtracted safely.
    """

    def __init__(
        self,
        root: Path | str,
        profile: AcquisitionProfile | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.generations = self.root / "generations"
        self.generations.mkdir(exist_ok=True)
        self._lock_path = self.root / ".writer.lock"
        self._closed = False
        try:
            descriptor = json.dumps(
                {"pid": os.getpid(), "started_ns": time.time_ns()},
                sort_keys=True,
            ).encode("ascii")
            fd = os.open(self._lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "wb") as handle:
                handle.write(descriptor)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError as exc:
            raise EventError(f"raw-event store already has a writer: {self.root}") from exc
        try:
            self._rows: list[dict[str, Any]] = []
            self._generation = 0
            self._profile = profile or AcquisitionProfile()
            self._learner = RawEventLearner(self._profile)
            current = self.root / "CURRENT"
            if current.is_file():
                if profile is not None:
                    requested_profile = profile
                else:
                    requested_profile = None
                self._load_current(requested_profile)
            else:
                self._commit(reason="initialize")
        except Exception:
            self.close()
            raise

    @property
    def learner(self) -> RawEventLearner:
        self._require_open()
        return self._learner

    @property
    def profile(self) -> AcquisitionProfile:
        return self._profile

    def _require_open(self) -> None:
        if self._closed:
            raise EventError("raw-event store is closed")

    def _generation_name(self, value: int) -> str:
        return f"gen-{value:08d}"

    def _load_current(self, requested_profile: AcquisitionProfile | None) -> None:
        pointer = (self.root / "CURRENT").read_text(encoding="ascii").strip()
        expected_name = self._generation_name(int(pointer.removeprefix("gen-")))
        if pointer != expected_name:
            raise CheckpointError("CURRENT points to an invalid generation name")
        directory = self.generations / pointer
        if not directory.is_dir():
            raise CheckpointError("CURRENT generation is missing")
        manifest_bytes = (directory / "manifest.json").read_bytes()
        try:
            manifest = json.loads(manifest_bytes.decode("utf-8"))
        except Exception as exc:
            raise CheckpointError(f"generation manifest is invalid: {exc}") from exc
        if not isinstance(manifest, Mapping) or manifest.get("schema") != _GENERATION_SCHEMA:
            raise CheckpointError("generation manifest schema mismatch")
        checkpoint = (directory / "field.chk").read_bytes()
        journal = (directory / "journal.jsonl").read_bytes()
        if manifest.get("checkpoint_sha256") != _sha(checkpoint):
            raise CheckpointError("generation checkpoint digest mismatch")
        if manifest.get("journal_sha256") != _sha(journal):
            raise CheckpointError("generation journal digest mismatch")
        if manifest.get("journal_bytes") != len(journal):
            raise CheckpointError("generation journal byte count mismatch")
        rows = _parse_journal(journal)
        if manifest.get("event_count") != len(rows):
            raise CheckpointError("generation event count mismatch")
        learner = RawEventLearner.restore(checkpoint)
        if manifest.get("state_sha256") != learner.fingerprint():
            raise CheckpointError("generation state identity mismatch")
        if manifest.get("profile_sha256") != learner.profile.fingerprint:
            raise CheckpointError("generation profile identity mismatch")
        if requested_profile is not None and requested_profile != learner.profile:
            raise CheckpointError("store belongs to a different acquisition profile")
        active_events = [
            RawEvent.from_dict(row["event"]) for row in rows if not row["revoked"]
        ]
        learner.restore_context_from_events(active_events)
        self._generation = int(manifest["generation"])
        if pointer != self._generation_name(self._generation):
            raise CheckpointError("generation number and directory disagree")
        self._rows = rows
        self._profile = learner.profile
        self._learner = learner

    def _commit(self, *, reason: str) -> dict[str, Any]:
        if self._generation >= _MAX_GENERATIONS:
            raise EventError("store generation capacity is exhausted")
        checkpoint = self._learner.checkpoint_bytes()
        journal = _journal_bytes(self._rows)
        if len(self._rows) > _MAX_EVENTS:
            raise EventError("event journal capacity is exhausted")
        if len(journal) > _MAX_JOURNAL_BYTES:
            raise EventError("event journal byte capacity is exhausted")
        generation = self._generation + 1
        name = self._generation_name(generation)
        final_directory = self.generations / name
        if final_directory.exists():
            raise CheckpointError("immutable generation already exists")
        temporary = Path(
            tempfile.mkdtemp(prefix=f".{name}.", dir=self.generations)
        )
        manifest = {
            "schema": _GENERATION_SCHEMA,
            "store_schema": _STORE_SCHEMA,
            "generation": generation,
            "reason": reason,
            "profile_sha256": self._profile.fingerprint,
            "state_sha256": self._learner.fingerprint(),
            "checkpoint_sha256": _sha(checkpoint),
            "checkpoint_bytes": len(checkpoint),
            "journal_sha256": _sha(journal),
            "journal_bytes": len(journal),
            "event_count": len(self._rows),
            "active_event_count": sum(not row["revoked"] for row in self._rows),
            "last_sequence": 0 if not self._rows else self._rows[-1]["event"]["seq"],
        }
        try:
            (temporary / "field.chk").write_bytes(checkpoint)
            (temporary / "journal.jsonl").write_bytes(journal)
            (temporary / "manifest.json").write_bytes(_canonical(manifest))
            os.replace(temporary, final_directory)
            _atomic_write(self.root / "CURRENT", (name + "\n").encode("ascii"))
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        self._generation = generation
        return manifest

    def admit(
        self,
        event: RawEvent,
        *,
        learn: bool = True,
        promote: bool = True,
    ) -> dict[str, Any]:
        self._require_open()
        if not isinstance(event, RawEvent):
            raise EventError("admit requires a RawEvent")
        if not isinstance(learn, bool) or not isinstance(promote, bool):
            raise EventError("learn and promote must be booleans")
        expected = 1 if not self._rows else int(self._rows[-1]["event"]["seq"]) + 1
        if event.seq < expected:
            existing = next(
                (
                    row
                    for row in self._rows
                    if int(row["event"]["seq"]) == event.seq
                ),
                None,
            )
            if (
                existing is not None
                and existing["event"] == event.to_dict()
                and existing["learn"] == learn
                and existing["promote"] == promote
            ):
                return {
                    "schema": "cassi.raw-event-store-admission.v1",
                    "status": "duplicate",
                    "sequence": event.seq,
                    "generation": self._generation,
                    "state_sha256": self._learner.fingerprint(),
                    "mutated": False,
                }
            raise EventError(f"sequence {event.seq} conflicts with the durable journal")
        if event.seq != expected:
            raise EventError(f"event sequence must be contiguous; expected {expected}")
        if len(self._rows) >= _MAX_EVENTS:
            raise EventError("event journal capacity is exhausted")
        predecessor = self._learner.fingerprint()
        learner_before = self._learner.clone()
        row = {
            "event": event.to_dict(),
            "learn": learn,
            "promote": promote,
            "revoked": False,
        }
        self._rows.append(row)
        try:
            transition = self._learner.apply(event, learn=learn, promote=promote)
            manifest = self._commit(reason="admit")
        except Exception:
            self._rows.pop()
            self._learner = learner_before
            raise
        return {
            "schema": "cassi.raw-event-store-admission.v1",
            "status": "committed",
            "sequence": event.seq,
            "generation": self._generation,
            "predecessor_state_sha256": predecessor,
            "state_sha256": self._learner.fingerprint(),
            "mutated": predecessor != self._learner.fingerprint(),
            "transition": transition,
            "generation_manifest": manifest,
        }

    def revoke(self, sequence: int) -> dict[str, Any]:
        self._require_open()
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
            raise EventError("revocation sequence must be a positive integer")
        target_index = next(
            (
                index
                for index, row in enumerate(self._rows)
                if int(row["event"]["seq"]) == sequence
            ),
            None,
        )
        if target_index is None:
            raise EventError(f"sequence {sequence} does not exist")
        if self._rows[target_index]["revoked"]:
            return {
                "schema": "cassi.raw-event-store-revocation.v1",
                "status": "duplicate",
                "sequence": sequence,
                "generation": self._generation,
                "state_sha256": self._learner.fingerprint(),
                "mutated": False,
            }
        start = target_index
        while start > 0 and self._rows[start]["event"]["kind"] != "reset":
            start -= 1
        if self._rows[start]["event"]["kind"] != "reset":
            start = 0
        end = target_index + 1
        while end < len(self._rows) and self._rows[end]["event"]["kind"] != "reset":
            end += 1
        previous_rows = [dict(row) for row in self._rows]
        previous_learner = self._learner
        revoked_sequences = [
            int(self._rows[index]["event"]["seq"]) for index in range(start, end)
        ]
        for index in range(start, end):
            self._rows[index] = {**self._rows[index], "revoked": True}
        started = time.perf_counter()
        rebuilt = RawEventLearner(self._profile)
        replayed = 0
        try:
            for row in self._rows:
                if row["revoked"]:
                    continue
                rebuilt.apply(
                    RawEvent.from_dict(row["event"]),
                    learn=bool(row["learn"]),
                    promote=bool(row["promote"]),
                )
                replayed += 1
            self._learner = rebuilt
            manifest = self._commit(reason="revoke-episode-and-rebuild")
        except Exception:
            self._rows = previous_rows
            self._learner = previous_learner
            raise
        elapsed = time.perf_counter() - started
        return {
            "schema": "cassi.raw-event-store-revocation.v1",
            "status": "committed",
            "sequence": sequence,
            "scope": "entire-reset-bounded-episode",
            "revoked_sequences": revoked_sequences,
            "replayed_events": replayed,
            "rebuild_seconds": elapsed,
            "generation": self._generation,
            "state_sha256": self._learner.fingerprint(),
            "mutated": previous_learner.fingerprint() != self._learner.fingerprint(),
            "generation_manifest": manifest,
        }

    def snapshot(self) -> dict[str, Any]:
        self._require_open()
        return {
            "schema": "cassi.raw-event-store-snapshot.v1",
            "root": str(self.root),
            "generation": self._generation,
            "event_count": len(self._rows),
            "active_event_count": sum(not row["revoked"] for row in self._rows),
            "revoked_event_count": sum(row["revoked"] for row in self._rows),
            "last_sequence": 0 if not self._rows else self._rows[-1]["event"]["seq"],
            "limits": {
                "events": _MAX_EVENTS,
                "generations": _MAX_GENERATIONS,
                "journal_bytes": _MAX_JOURNAL_BYTES,
            },
            "field": self._learner.snapshot(),
        }

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._lock_path.unlink(missing_ok=True)
        except OSError:
            pass

    def __enter__(self) -> "RawEventStore":
        self._require_open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()


__all__ = ["RawEventStore"]
