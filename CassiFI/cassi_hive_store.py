"""Durable local storage for Cassi Hive semantic artifacts.

The store is a control-plane component.  It persists immutable, content-
addressed capsules, reviews, bundles, session manifests, and adoption receipts;
it never stores or merges an adaptive field tensor.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from cassi_field_atlas import canonical_json_bytes, sha256_value
from cassi_field_hive import (
    BUNDLE_SCHEMA,
    EXPERIENCE_SCHEMA,
    ADOPTION_SCHEMA,
    AdoptionReceipt,
    ExperienceCandidate,
    ExperienceCapsule,
    ExperienceEpisode,
    ExperienceEvidence,
    ExperienceOrigin,
    HiveProtocolError,
    KnowledgeBundle,
    Review,
    TransferSpec,
    verify_object_digest,
)


STORE_SCHEMA = "cassifi.hive.store.v1"
SESSION_SCHEMA = "cassifi.hive.session.v1"
REVIEW_SCHEMA = "cassifi.hive.review.v1"
EVENT_SCHEMA = "cassifi.hive.event.v1"
FORK_SCHEMA = "cassifi.hive.fork.v1"
REVOCATION_SCHEMA = "cassifi.hive.revocation.v1"

AUDIT_SCHEMA = "cassifi.hive.audit.v1"
DEFAULT_HIVE_HOME = Path(__file__).resolve().parents[1] / ".cassi" / "hive"

class HiveStoreError(RuntimeError):
    """Raised when the durable hive control plane cannot make progress."""


def make_document(schema: str, content: Mapping[str, Any]) -> dict[str, Any]:
    """Build a canonical content-addressed hive document."""

    if not isinstance(schema, str) or not schema:
        raise HiveStoreError("document schema must be nonempty text")
    if not isinstance(content, Mapping):
        raise HiveStoreError("document content must be a mapping")
    try:
        normalized = json.loads(canonical_json_bytes(content).decode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise HiveStoreError("document content must be canonical JSON") from exc
    if not isinstance(normalized, dict):
        raise HiveStoreError("document content must encode an object")
    object_id = sha256_value({"schema": schema, "content": normalized})
    return {
        "content": normalized,
        "content_sha256": object_id,
        "object_id": object_id,
        "schema": schema,
    }


def _verify_document(document: Mapping[str, Any]) -> str:
    if not isinstance(document, Mapping):
        raise HiveStoreError("stored object must be a mapping")
    schema = document.get("schema")
    content = document.get("content")
    declared = document.get("content_sha256")
    object_id = document.get("object_id")
    if not isinstance(schema, str) or not isinstance(content, Mapping):
        raise HiveStoreError("stored object envelope is malformed")
    if not isinstance(declared, str) or declared != object_id:
        raise HiveStoreError("stored object identity is malformed")
    expected = sha256_value({"schema": schema, "content": content})
    if expected != declared:
        raise HiveStoreError("stored object digest does not match its content")
    if schema in {EXPERIENCE_SCHEMA, BUNDLE_SCHEMA, ADOPTION_SCHEMA} and not verify_object_digest(document):
        raise HiveStoreError("protocol object digest verification failed")
    return declared


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.replace(temporary, path)
        except OSError as exc:
            try:
                existing = path.read_bytes()
            except OSError:
                raise exc
            if existing != payload:
                raise exc
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _bounded_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise HiveStoreError(f"{label} must be a lowercase SHA-256 digest")
    return value


class LocalHiveStore:
    """SQLite-indexed, content-addressed local hive backend.

    One store can be opened by many test processes.  SQLite WAL transactions
    serialize generation advancement, while immutable object files make every
    payload independently inspectable and reproducible.
    """

    def __init__(self, root: Path, *, hive_id: str, branch: str = "main") -> None:
        if not isinstance(hive_id, str) or not hive_id:
            raise HiveStoreError("hive_id must be nonempty text")
        if not isinstance(branch, str) or not branch:
            raise HiveStoreError("branch must be nonempty text")
        self.root = Path(root).expanduser()
        self.hive_id = hive_id
        self.branch = branch
        self.objects = self.root / "objects"
        self.events = self.root / "events"
        self.receipts = self.root / "receipts"
        self.quarantine = self.root / "quarantine"
        for directory in (self.objects, self.events, self.receipts, self.quarantine):
            directory.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "index.sqlite"
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            isolation_level=None,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS objects (
                    object_id TEXT PRIMARY KEY,
                    schema TEXT NOT NULL,
                    path TEXT NOT NULL UNIQUE,
                    inserted_ns INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    branch TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    event_kind TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    inserted_ns INTEGER NOT NULL,
                    UNIQUE(branch, event_kind, object_id)
                );
                CREATE INDEX IF NOT EXISTS events_branch_generation
                    ON events(branch, generation, event_kind);
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    instance_id TEXT NOT NULL,
                    manifest_object_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_ns INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS adoptions (
                    receipt_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    instance_id TEXT NOT NULL,
                    bundle_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    inserted_ns INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS adoptions_session
                    ON adoptions(session_id, inserted_ns);
                CREATE TABLE IF NOT EXISTS revocations (
                    bundle_id TEXT PRIMARY KEY,
                    object_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    inserted_ns INTEGER NOT NULL
                );
                """
            )
            key = self._generation_key(self.branch)
            self._connection.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES(?, ?)",
                (key, "0"),
            )

    @staticmethod
    def _generation_key(branch: str) -> str:
        return f"generation:{branch}"

    @property
    def current_generation(self) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT value FROM meta WHERE key = ?",
                (self._generation_key(self.branch),),
            ).fetchone()
            if row is None:
                raise HiveStoreError("hive generation metadata is missing")
            return int(row["value"])

    def put_document(self, document: Mapping[str, Any]) -> str:
        object_id = _verify_document(document)
        encoded = canonical_json_bytes(document)
        path = self.objects / object_id
        with self._lock:
            if path.exists():
                if path.read_bytes() != encoded:
                    raise HiveStoreError("content-addressed object collision")
            else:
                _atomic_write(path, encoded)
            now = time.time_ns()
            try:
                self._connection.execute(
                    "INSERT INTO objects(object_id, schema, path, inserted_ns) VALUES(?, ?, ?, ?)",
                    (object_id, str(document["schema"]), str(path), now),
                )
            except sqlite3.IntegrityError:
                existing = self._connection.execute(
                    "SELECT path FROM objects WHERE object_id = ?",
                    (object_id,),
                ).fetchone()
                if existing is None or Path(existing["path"]).read_bytes() != encoded:
                    raise HiveStoreError("indexed object differs from stored object")
            return object_id

    def get_document(self, object_id: str) -> dict[str, Any]:
        object_id = _bounded_digest(object_id, "object_id")
        with self._lock:
            row = self._connection.execute(
                "SELECT path FROM objects WHERE object_id = ?",
                (object_id,),
            ).fetchone()
            path = Path(row["path"]) if row is not None else self.objects / object_id
            try:
                encoded = path.read_bytes()
            except OSError as exc:
                raise HiveStoreError("stored object is unavailable") from exc
            try:
                document = json.loads(encoded.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise HiveStoreError("stored object is not valid JSON") from exc
            if not isinstance(document, dict) or _verify_document(document) != object_id:
                raise HiveStoreError("stored object identity is corrupt")
            if canonical_json_bytes(document) != encoded:
                raise HiveStoreError("stored object is not canonical JSON")
            return document

    def has_object(self, object_id: str) -> bool:
        try:
            self.get_document(object_id)
        except HiveStoreError:
            return False
        return True

    def list_documents(self, *, schema: str | None = None) -> tuple[dict[str, Any], ...]:
        with self._lock:
            if schema is None:
                rows = self._connection.execute(
                    "SELECT object_id FROM objects ORDER BY inserted_ns, object_id"
                ).fetchall()
            else:
                rows = self._connection.execute(
                    "SELECT object_id FROM objects WHERE schema = ? ORDER BY inserted_ns, object_id",
                    (schema,),
                ).fetchall()
            return tuple(self.get_document(row["object_id"]) for row in rows)

    def audit(self) -> Mapping[str, Any]:
        """Return a read-only integrity and reconciliation report.

        The report deliberately does not delete or repair anything.  A valid
        object file without an index row is both ``unindexed`` and
        ``orphaned``; a valid indexed bundle without a branch event is
        ``unpublished`` and remains available for an explicit retry.
        """

        with self._lock:
            indexed_rows = self._connection.execute(
                "SELECT object_id, schema, path FROM objects ORDER BY object_id"
            ).fetchall()
            indexed_ids = {str(row["object_id"]) for row in indexed_rows}
            indexed_paths = {str(row["object_id"]): Path(row["path"]) for row in indexed_rows}
            event_rows = self._connection.execute(
                "SELECT event_kind, object_id FROM events WHERE branch = ? ORDER BY sequence",
                (self.branch,),
            ).fetchall()
            object_files: dict[str, Path] = {}
            temporary_paths: list[str] = []
            for path in sorted(self.objects.iterdir(), key=lambda item: item.name):
                if not path.is_file():
                    continue
                if path.name.startswith(".") and path.name.endswith(".tmp"):
                    temporary_paths.append(str(path.relative_to(self.root)))
                    continue
                if len(path.name) == 64 and all(char in "0123456789abcdef" for char in path.name):
                    object_files[path.name] = path

            valid_documents: dict[str, Mapping[str, Any]] = {}
            corrupt_ids: list[str] = []
            corrupt_errors: dict[str, str] = {}
            for object_id, path in sorted(object_files.items()):
                try:
                    encoded = path.read_bytes()
                    document = json.loads(encoded.decode("utf-8"))
                    if not isinstance(document, dict) or _verify_document(document) != object_id:
                        raise HiveStoreError("stored object identity is corrupt")
                    if canonical_json_bytes(document) != encoded:
                        raise HiveStoreError("stored object is not canonical JSON")
                except Exception as exc:
                    corrupt_ids.append(object_id)
                    corrupt_errors[object_id] = str(exc)
                else:
                    valid_documents[object_id] = document

            schema_mismatches = sorted(
                object_id
                for object_id, path in indexed_paths.items()
                if object_id in valid_documents
                and next(row["schema"] for row in indexed_rows if row["object_id"] == object_id)
                != valid_documents[object_id]["schema"]
            )
            event_object_ids = {str(row["object_id"]) for row in event_rows}
            published_bundle_ids = {
                str(row["object_id"]) for row in event_rows if row["event_kind"] == "bundle"
            }
            valid_bundle_ids = {
                object_id
                for object_id, document in valid_documents.items()
                if document.get("schema") == BUNDLE_SCHEMA
            }
            unindexed_ids = sorted(set(object_files) - indexed_ids)
            orphaned_ids = sorted(set(valid_documents) - indexed_ids)
            missing_indexed_ids = sorted(indexed_ids - set(object_files))
            dangling_event_ids = sorted(event_object_ids - set(valid_documents))
            unpublished_bundle_ids = sorted(valid_bundle_ids - published_bundle_ids)
            clean = not any(
                (
                    temporary_paths,
                    corrupt_ids,
                    schema_mismatches,
                    unindexed_ids,
                    missing_indexed_ids,
                    dangling_event_ids,
                    unpublished_bundle_ids,
                )
            )
            return {
                "audit_schema": AUDIT_SCHEMA,
                "branch": self.branch,
                "clean": clean,
                "corrupt_errors": dict(sorted(corrupt_errors.items())),
                "corrupt_object_ids": sorted(corrupt_ids),
                "dangling_event_object_ids": dangling_event_ids,
                "hive_id": self.hive_id,
                "index_schema_mismatch_object_ids": schema_mismatches,
                "missing_indexed_object_ids": missing_indexed_ids,
                "object_file_ids": sorted(object_files),
                "orphaned_object_ids": orphaned_ids,
                "published_bundle_ids": sorted(published_bundle_ids),
                "temporary_object_paths": sorted(temporary_paths),
                "unindexed_object_ids": unindexed_ids,
                "unpublished_bundle_ids": unpublished_bundle_ids,
                "counts": {
                    "corrupt_objects": len(corrupt_ids),
                    "indexed_objects": len(indexed_ids),
                    "missing_indexed_objects": len(missing_indexed_ids),
                    "object_files": len(object_files),
                    "orphaned_objects": len(orphaned_ids),
                    "published_bundles": len(published_bundle_ids),
                    "temporary_paths": len(temporary_paths),
                    "unindexed_objects": len(unindexed_ids),
                    "unpublished_bundles": len(unpublished_bundle_ids),
                },
            }

    def register_session(
        self,
        manifest: Mapping[str, Any],
        *,
        session_id: str,
        instance_id: str,
        status: str = "active",
    ) -> str:
        object_id = self.put_document(manifest)
        now = time.time_ns()
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                existing = self._connection.execute(
                    "SELECT manifest_object_id FROM sessions WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                if existing is not None and existing["manifest_object_id"] != object_id:
                    raise HiveStoreError("session identity is already bound to another manifest")
                self._connection.execute(
                    "INSERT INTO sessions(session_id, instance_id, manifest_object_id, status, updated_ns) "
                    "VALUES(?, ?, ?, ?, ?) "
                    "ON CONFLICT(session_id) DO UPDATE SET status=excluded.status, updated_ns=excluded.updated_ns",
                    (session_id, instance_id, object_id, status, now),
                )
                self._connection.execute("COMMIT")
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
        return object_id

    def update_session(self, session_id: str, status: str) -> None:
        with self._lock:
            self._connection.execute(
                "UPDATE sessions SET status = ?, updated_ns = ? WHERE session_id = ?",
                (status, time.time_ns(), session_id),
            )

    def put_capsule(self, capsule: Any) -> str:
        if not hasattr(capsule, "as_dict"):
            raise HiveStoreError("capsule must expose as_dict")
        document = capsule.as_dict()
        if document.get("schema") != EXPERIENCE_SCHEMA:
            raise HiveStoreError("capsule has an unsupported schema")
        return self.put_document(document)

    def list_capsules(self, *, hive_id: str | None = None) -> tuple[ExperienceCapsule, ...]:
        result: list[ExperienceCapsule] = []
        for document in self.list_documents(schema=EXPERIENCE_SCHEMA):
            capsule = decode_capsule(document)
            if hive_id is None or capsule.hive_id == hive_id:
                result.append(capsule)
        return tuple(result)

    def put_review(
        self,
        review: Review,
        *,
        candidate_object_id: str,
        source_experience_ids: Sequence[str] = (),
    ) -> str:
        if not isinstance(review, Review):
            raise HiveStoreError("review must be a Review")
        content = {
            "candidate_object_id": _bounded_digest(candidate_object_id, "candidate_object_id"),
            "review": dict(review.as_dict()),
            "source_experience_ids": list(source_experience_ids),
        }
        return self.put_document(make_document(REVIEW_SCHEMA, content))

    def list_reviews(self, *, candidate_object_id: str | None = None) -> tuple[Review, ...]:
        result: list[Review] = []
        for document in self.list_documents(schema=REVIEW_SCHEMA):
            content = document["content"]
            if candidate_object_id is not None and content.get("candidate_object_id") != candidate_object_id:
                continue
            result.append(_decode_review(content["review"]))
        return tuple(result)

    def publish_bundle(self, bundle: KnowledgeBundle, *, expected_generation: int | None = None) -> str:
        if not isinstance(bundle, KnowledgeBundle):
            raise HiveStoreError("bundle must be a KnowledgeBundle")
        if bundle.hive_id != self.hive_id:
            raise HiveStoreError("bundle belongs to another hive")
        object_id = self.put_document(bundle.as_dict())
        expected = bundle.predecessor_common_generation if expected_generation is None else expected_generation
        if expected != bundle.predecessor_common_generation:
            raise HiveStoreError("expected generation differs from bundle predecessor")
        event_id = sha256_value(
            {
                "branch": self.branch,
                "generation": bundle.resulting_common_generation,
                "kind": "bundle",
                "object_id": object_id,
            }
        )
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                current = self.current_generation
                existing = self._connection.execute(
                    "SELECT generation FROM events WHERE branch = ? AND event_kind = ? AND object_id = ?",
                    (self.branch, "bundle", object_id),
                ).fetchone()
                if existing is not None:
                    self._connection.execute("COMMIT")
                    return object_id
                if current != expected:
                    raise HiveStoreError(
                        f"hive generation conflict: expected {expected}, current {current}"
                    )
                if bundle.resulting_common_generation != current + 1:
                    raise HiveStoreError("bundle does not advance the current hive generation")
                self._connection.execute(
                    "INSERT INTO events(event_id, branch, generation, event_kind, object_id, inserted_ns) "
                    "VALUES(?, ?, ?, ?, ?, ?)",
                    (event_id, self.branch, bundle.resulting_common_generation, "bundle", object_id, time.time_ns()),
                )
                self._connection.execute(
                    "UPDATE meta SET value = ? WHERE key = ?",
                    (str(bundle.resulting_common_generation), self._generation_key(self.branch)),
                )
                self._connection.execute("COMMIT")
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
        return object_id

    def list_bundle_documents(self, *, after_generation: int = 0) -> tuple[dict[str, Any], ...]:
        if isinstance(after_generation, bool) or not isinstance(after_generation, int) or after_generation < 0:
            raise HiveStoreError("after_generation must be a nonnegative integer")
        with self._lock:
            rows = self._connection.execute(
                "SELECT object_id FROM events WHERE branch = ? AND event_kind = 'bundle' "
                "AND generation > ? ORDER BY generation",
                (self.branch, after_generation),
            ).fetchall()
            return tuple(self.get_document(row["object_id"]) for row in rows)

    def list_bundles(self, *, after_generation: int = 0) -> tuple[KnowledgeBundle, ...]:
        return tuple(decode_bundle(document) for document in self.list_bundle_documents(after_generation=after_generation))

    def record_adoption(self, receipt: AdoptionReceipt, *, session_id: str) -> str:
        if not isinstance(receipt, AdoptionReceipt):
            raise HiveStoreError("adoption receipt must be an AdoptionReceipt")
        object_id = self.put_document(receipt.as_dict())
        with self._lock:
            self._connection.execute(
                "INSERT OR IGNORE INTO adoptions(receipt_id, session_id, instance_id, bundle_id, status, object_id, inserted_ns) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                (
                    receipt.object_id,
                    session_id,
                    receipt.recipient_instance_id,
                    receipt.bundle_id,
                    receipt.status,
                    object_id,
                    time.time_ns(),
                ),
            )
        _atomic_write(self.receipts / receipt.object_id, canonical_json_bytes(receipt.as_dict()))
        return object_id

    def list_adoptions(self, *, instance_id: str | None = None) -> tuple[dict[str, Any], ...]:
        with self._lock:
            if instance_id is None:
                rows = self._connection.execute(
                    "SELECT object_id FROM adoptions ORDER BY inserted_ns, receipt_id"
                ).fetchall()
            else:
                rows = self._connection.execute(
                    "SELECT object_id FROM adoptions WHERE instance_id = ? ORDER BY inserted_ns, receipt_id",
                    (instance_id,),
                ).fetchall()
            return tuple(self.get_document(row["object_id"]) for row in rows)

    def revoke_bundle(self, bundle_id: str, *, reason: str, actor: str) -> str:
        bundle_id = _bounded_digest(bundle_id, "bundle_id")
        try:
            bundle_document = self.get_document(bundle_id)
        except HiveStoreError as exc:
            raise HiveStoreError("cannot revoke an unavailable bundle") from exc
        if bundle_document.get("schema") != BUNDLE_SCHEMA:
            raise HiveStoreError("revocation target is not a knowledge bundle")
        if not isinstance(reason, str) or not reason:
            raise HiveStoreError("revocation reason must be nonempty text")
        if not isinstance(actor, str) or not actor:
            raise HiveStoreError("revocation actor must be nonempty text")
        document = make_document(
            REVOCATION_SCHEMA,
            {
                "actor": actor,
                "bundle_id": bundle_id,
                "reason": reason,
            },
        )
        object_id = self.put_document(document)
        with self._lock:
            self._connection.execute(
                "INSERT OR IGNORE INTO revocations(bundle_id, object_id, actor, reason, inserted_ns) "
                "VALUES(?, ?, ?, ?, ?)",
                (bundle_id, object_id, actor, reason, time.time_ns()),
            )
        return object_id

    def revoked_bundle_ids(self) -> tuple[str, ...]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT bundle_id FROM revocations ORDER BY inserted_ns, bundle_id"
            ).fetchall()
            return tuple(row["bundle_id"] for row in rows)

    def is_revoked(self, bundle_id: str) -> bool:
        bundle_id = _bounded_digest(bundle_id, "bundle_id")
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM revocations WHERE bundle_id = ?",
                (bundle_id,),
            ).fetchone()
            return row is not None

    def revocation(self, bundle_id: str) -> Mapping[str, Any] | None:
        bundle_id = _bounded_digest(bundle_id, "bundle_id")
        with self._lock:
            row = self._connection.execute(
                "SELECT object_id FROM revocations WHERE bundle_id = ?",
                (bundle_id,),
            ).fetchone()
            if row is None:
                return None
            return self.get_document(row["object_id"])

    def has_adoption(self, *, bundle_id: str, instance_id: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM adoptions WHERE bundle_id = ? AND instance_id = ? LIMIT 1",
                (bundle_id, instance_id),
            ).fetchone()
            return row is not None

    def status(self) -> Mapping[str, Any]:
        with self._lock:
            objects = self._connection.execute("SELECT COUNT(*) AS count FROM objects").fetchone()["count"]
            sessions = self._connection.execute("SELECT COUNT(*) AS count FROM sessions").fetchone()["count"]
            bundles = self._connection.execute(
                "SELECT COUNT(*) AS count FROM events WHERE branch = ? AND event_kind = 'bundle'",
                (self.branch,),
            ).fetchone()["count"]
            adoptions = self._connection.execute("SELECT COUNT(*) AS count FROM adoptions").fetchone()["count"]
            revoked = self._connection.execute("SELECT COUNT(*) AS count FROM revocations").fetchone()["count"]
        return {
            "branch": self.branch,
            "current_generation": self.current_generation,
            "hive_id": self.hive_id,
            "object_count": int(objects),
            "session_count": int(sessions),
            "bundle_count": int(bundles),
            "adoption_count": int(adoptions),
            "root": str(self.root),
            "schema": STORE_SCHEMA,
            "revoked_bundle_count": int(revoked),
        }

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None  # type: ignore[assignment]

    def __enter__(self) -> "LocalHiveStore":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


def _decode_review(value: Mapping[str, Any]) -> Review:
    if not isinstance(value, Mapping):
        raise HiveStoreError("review payload is malformed")
    return Review(
        reviewer_instance_id=value["reviewer_instance_id"],
        review_type=value["review_type"],
        result=value["result"],
        evidence_ids=tuple(value["evidence_ids"]),
    )


def decode_capsule(document: Mapping[str, Any]) -> ExperienceCapsule:
    if _verify_document(document) != document.get("object_id") or document.get("schema") != EXPERIENCE_SCHEMA:
        raise HiveStoreError("experience document is invalid")
    content = document["content"]
    try:
        origin = content["origin"]
        episode = content["episode"]
        candidate = content["candidate"]
        evidence = content["evidence"]
        transfer = content["transfer"]
        return ExperienceCapsule(
            hive_id=content["hive_id"],
            origin=ExperienceOrigin(
                instance_id=origin["instance_id"],
                role=origin["role"],
                field_profile_sha256=origin["field_profile_sha256"],
                atlas_schema=origin["atlas_schema"],
                predecessor_manifest_sha256=origin["predecessor_manifest_sha256"],
                predecessor_state_sha256=origin["predecessor_state_sha256"],
                successor_manifest_sha256=origin["successor_manifest_sha256"],
                successor_state_sha256=origin["successor_state_sha256"],
                local_generation=origin["local_generation"],
                common_generation=origin["common_generation"],
            ),
            episode=ExperienceEpisode(
                task_id=episode["task_id"],
                context=episode["context"],
                source_revision_ids=tuple(episode["source_revision_ids"]),
                observation_event_ids=tuple(episode["observation_event_ids"]),
                action=episode["action"],
                prediction=episode["prediction"],
                outcome=episode["outcome"],
                work_units=episode["work_units"],
                uncertainty=episode["uncertainty"],
            ),
            candidate=ExperienceCandidate(
                kind=candidate["kind"],
                object=candidate["object"],
                operation_plan=tuple(candidate["operation_plan"]),
                guards=tuple(candidate["guards"]),
                dependencies=tuple(candidate["dependencies"]),
            ),
            evidence=ExperienceEvidence(
                support_event_ids=tuple(evidence["support_event_ids"]),
                assessment_ids=tuple(evidence["assessment_ids"]),
                held_out_results=tuple(evidence["held_out_results"]),
                counterexamples=tuple(evidence["counterexamples"]),
                derivation_roots=tuple(evidence["derivation_roots"]),
            ),
            transfer=TransferSpec(
                required_field_profile_sha256=transfer["required_field_profile_sha256"],
                required_atlas_schema=transfer["required_atlas_schema"],
                replay_mode=transfer["replay_mode"],
                maximum_admission_work=transfer["maximum_admission_work"],
                visibility=transfer["visibility"],
            ),
        )
    except (KeyError, TypeError, ValueError, HiveProtocolError) as exc:
        raise HiveStoreError("experience document cannot be decoded") from exc


def decode_bundle(document: Mapping[str, Any]) -> KnowledgeBundle:
    if _verify_document(document) != document.get("object_id") or document.get("schema") != BUNDLE_SCHEMA:
        raise HiveStoreError("bundle document is invalid")
    content = document["content"]
    try:
        return KnowledgeBundle(
            hive_id=content["hive_id"],
            leader_instance_id=content["leader_instance_id"],
            authority_grant_sha256=content["authority_grant_sha256"],
            predecessor_common_generation=content["predecessor_common_generation"],
            resulting_common_generation=content["resulting_common_generation"],
            source_experience_ids=tuple(content["source_experience_ids"]),
            learned_objects=tuple(content["learned_objects"]),
            operation_plan=tuple(content["operation_plan"]),
            guards=tuple(content["guards"]),
            dependencies=tuple(content["dependencies"]),
            compatibility=content["compatibility"],
            reviews=tuple(_decode_review(item) for item in content["reviews"]),
            known_exceptions=tuple(content["known_exceptions"]),
            revocation_conditions=tuple(content["revocation_conditions"]),
            status=content.get("status", "promoted"),
        )
    except (KeyError, TypeError, ValueError, HiveProtocolError) as exc:
        raise HiveStoreError("bundle document cannot be decoded") from exc


__all__ = [
    "AUDIT_SCHEMA",
    "DEFAULT_HIVE_HOME",
    "ADOPTION_SCHEMA",
    "BUNDLE_SCHEMA",
    "EVENT_SCHEMA",
    "EXPERIENCE_SCHEMA",
    "FORK_SCHEMA",
    "HiveStoreError",
    "LocalHiveStore",
    "REVIEW_SCHEMA",
    "SESSION_SCHEMA",
    "STORE_SCHEMA",
    "decode_bundle",
    "decode_capsule",
    "make_document",
    "REVOCATION_SCHEMA",
]
