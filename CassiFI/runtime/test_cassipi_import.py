from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_cassipi_runtime import build_runtime
from cassi_cassipi_v2 import CanonicalOwnerAdapter
from cassi_cassipi_import import CassiPiLegacyImporter, ImportError as CassiPiImportError


class _InterruptAfterOneObserve:
    def __init__(self, adapter: CanonicalOwnerAdapter) -> None:
        self.adapter = adapter
        self.observations = 0

    def __getattr__(self, name: str):
        return getattr(self.adapter, name)

    def observe(self, request):
        if self.observations == 1:
            raise RuntimeError("injected import interruption")
        self.observations += 1
        return self.adapter.observe(request)


SCOPE = {
    "profile_id": "profile-a",
    "project_id": "project-a",
    "session_id": "session-a",
    "branch_id": "branch-a",
    "task_scope": "task-a",
}


def _preview(importer: CassiPiLegacyImporter, adapter: str, path: Path):
    return importer.preview(
        {
            "schema": "cassipi.import-preview.v1",
            "adapter": adapter,
            "source_path": str(path),
            "memory_scope": "project",
            **SCOPE,
        }
    )


def _mnemic(path: Path) -> None:
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE mnemic_field_events (
          stream_id TEXT NOT NULL,
          sequence INTEGER NOT NULL,
          previous_event_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          payload TEXT NOT NULL,
          created_at INTEGER NOT NULL
        );
        """
    )
    db.executemany(
        "INSERT INTO mnemic_field_events VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                "stream-a",
                1,
                "0" * 64,
                "1" * 64,
                '{"kind":"memory","record":{"content":"alpha"}}',
                1_700_000_000_000,
            ),
            (
                "stream-a",
                2,
                "1" * 64,
                "2" * 64,
                '{"kind":"corrected","record":{"content":"beta","source_refs":["1"]}}',
                1_700_000_001_000,
            ),
            (
                "stream-a",
                3,
                "2" * 64,
                "3" * 64,
                '{"kind":"invalidated","record":{"content":"stale"}}',
                1_700_000_002_000,
            ),
            (
                "stream-a",
                4,
                "3" * 64,
                "4" * 64,
                '{"kind":"source-gap","record":{"content":"missing source"}}',
                1_700_000_003_000,
            ),
        ],
    )
    db.commit()
    db.close()


def _thalamus(path: Path) -> None:
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE dropped_messages (
          id INTEGER PRIMARY KEY,
          session_id TEXT, pass_number INTEGER, msg_index INTEGER,
          role TEXT, content TEXT, slot TEXT, composite REAL, created_at TEXT
        );
        CREATE TABLE recall_queue (
          id INTEGER PRIMARY KEY,
          session_id TEXT, content TEXT, role TEXT, source TEXT, label TEXT, created_at TEXT
        );
        PRAGMA user_version = 3;
        """
    )
    db.execute(
        "INSERT INTO dropped_messages VALUES (1, 'legacy-session', 2, 3, 'user', 'remember water', 'request', 0.7, '2026-01-01T00:00:00Z')"
    )
    db.execute(
        "INSERT INTO recall_queue VALUES (1, 'legacy-session', 'water memory', 'user', 'recall', 'water', '2026-01-02T00:00:00Z')"
    )
    db.commit()
    db.close()


def _mnemopi(path: Path) -> None:
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE working_memory (
          id TEXT PRIMARY KEY, content TEXT NOT NULL, source TEXT,
          timestamp TEXT, session_id TEXT, importance REAL,
          metadata_json TEXT, scope TEXT, author_id TEXT
        );
        """
    )
    db.execute(
        "INSERT INTO working_memory VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("memory-a", "owner likes exact sources", "user", "2026-01-03T00:00:00Z", "legacy-session", 0.9, "{}", "global", "owner"),
    )
    db.commit()
    db.close()


def _omp_session(path: Path) -> None:
    rows = [
        {
            "type": "session",
            "version": 3,
            "id": "legacy-session",
            "timestamp": "2026-01-01T00:00:00Z",
            "cwd": "C:/legacy",
        },
        {
            "type": "message",
            "id": "entry-a",
            "parentId": None,
            "timestamp": "2026-01-01T00:00:01Z",
            "message": {"role": "user", "content": "alpha"},
        },
        {
            "type": "message",
            "id": "entry-b",
            "parentId": "entry-a",
            "timestamp": "2026-01-01T00:00:02Z",
            "message": {"role": "assistant", "content": "beta"},
        },
    ]
    path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


@pytest.mark.parametrize(
    ("adapter_name", "builder", "expected"),
    [
        ("mnemic", _mnemic, 4),
        ("thalamus", _thalamus, 2),
        ("mnemopi", _mnemopi, 1),
        ("omp-session", _omp_session, 2),
    ],
)
def test_previews_supported_legacy_stores_without_mutating_them(
    tmp_path: Path,
    adapter_name: str,
    builder,
    expected: int,
) -> None:
    source = tmp_path / ("session.jsonl" if adapter_name == "omp-session" else "legacy.db")
    builder(source)
    before = hashlib.sha256(source.read_bytes()).hexdigest()

    importer = CassiPiLegacyImporter(object(), tmp_path / "owner")
    preview = _preview(importer, adapter_name, source)

    assert preview["record_count"] == expected
    assert preview["adapter"] == adapter_name
    assert preview["duplicate_policy"] == "preserve-distinct-provenance"
    assert preview["source_file_sha256"] == before
    assert preview["missing_provenance_records"] == 0
    assert preview["required_disk_bytes"] > 0
    assert preview["disk_space_sufficient"] is True
    if adapter_name == "mnemopi":
        assert preview["wider_scope_records"] == 1
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_import_commit_is_source_bound_resumable_and_idempotent(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    build_runtime(runtime)
    source = tmp_path / "session.jsonl"
    _omp_session(source)
    adapter = CanonicalOwnerAdapter(runtime, data_home=tmp_path / "owner")
    interrupted = _InterruptAfterOneObserve(adapter)
    importer = CassiPiLegacyImporter(interrupted, tmp_path / "owner")
    preview = _preview(importer, "omp-session", source)
    request = {
        "schema": "cassipi.import-commit.v1",
        "preview_id": preview["preview_id"],
        **SCOPE,
    }

    with pytest.raises(RuntimeError, match="injected import interruption"):
        importer.commit(request)

    resumed = CassiPiLegacyImporter(adapter, tmp_path / "owner").commit(request)
    repeated = CassiPiLegacyImporter(adapter, tmp_path / "owner").commit(request)

    assert resumed["status"] == "committed"
    assert resumed["imported_records"] == 1
    assert resumed["already_committed_records"] == 1
    assert repeated["imported_records"] == 0
    assert repeated["already_committed_records"] == 2
    bindings = adapter.bindings(
        {
            "schema": "cassipi.host-bindings.v1",
            "profile_id": SCOPE["profile_id"],
            "project_id": SCOPE["project_id"],
            "session_id": SCOPE["session_id"],
            "branch_id": SCOPE["branch_id"],
            "producer_id": f"import:{preview['preview_id'][:32]}",
        }
    )
    assert len(bindings["bindings"]) == 2
    assert all(row["event_kind"] == "import" for row in bindings["bindings"])


def test_import_commit_rejects_source_changed_after_preview(tmp_path: Path) -> None:
    source = tmp_path / "session.jsonl"
    _omp_session(source)
    importer = CassiPiLegacyImporter(object(), tmp_path / "owner")
    preview = _preview(importer, "omp-session", source)
    source.write_text(
        source.read_text(encoding="utf-8").replace("beta", "changed"),
        encoding="utf-8",
    )
    with pytest.raises(CassiPiImportError, match="changed after preview"):
        importer.commit(
            {
                "schema": "cassipi.import-commit.v1",
                "preview_id": preview["preview_id"],
                **SCOPE,
            }
        )


def test_import_commit_rejects_tampered_persisted_binding_without_mutation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "session.jsonl"
    _omp_session(source)
    data_home = tmp_path / "owner"
    importer = CassiPiLegacyImporter(object(), data_home)
    preview = _preview(importer, "omp-session", source)
    plan_path = data_home / "imports" / f"{preview['preview_id']}.json"
    plan = json.loads(plan_path.read_bytes())
    plan["binding"]["memory_scope"] = "task"
    tampered = (
        json.dumps(
            plan,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    plan_path.write_bytes(tampered)

    with pytest.raises(CassiPiImportError) as failure:
        importer.commit(
            {
                "schema": "cassipi.import-commit.v1",
                "preview_id": preview["preview_id"],
                **SCOPE,
            }
        )
    assert failure.value.code == "IMPORT_PLAN_CORRUPT"
    assert plan_path.read_bytes() == tampered


def test_imported_terminal_records_remain_archival_not_projectable(
    tmp_path: Path,
) -> None:
    canonical_runtime = tmp_path / "runtime"
    build_runtime(canonical_runtime)
    source = tmp_path / "mnemic.db"
    _mnemic(source)
    adapter = CanonicalOwnerAdapter(canonical_runtime, data_home=tmp_path / "owner")
    importer = CassiPiLegacyImporter(adapter, tmp_path / "owner")
    preview = _preview(importer, "mnemic", source)
    assert preview["projection_eligible_records"] == 3
    assert preview["projection_ineligible_records"] == 1
    importer.commit(
        {
            "schema": "cassipi.import-commit.v1",
            "preview_id": preview["preview_id"],
            **SCOPE,
        }
    )
    status = adapter.owner_status()
    inventory = adapter.projection_inventory(
        {
            **SCOPE,
            "task": "inspect imported records",
            "expected_head_id": status["field_head_sha256"],
            "expected_journal_head_sha256": status["journal_head_sha256"],
            "expected_revocation_epoch": status["revocation_epoch"],
            "input_revision_sha256": "a" * 64,
            "provider_call_id": "import-inventory",
            "model_id": "test-model",
            "tokenizer_id": "exact-test-tokenizer",
            "allowed_memory_scopes": ["project"],
            "mandatory_revision_ids": [],
            "excluded_revision_ids": [],
        }
    )
    native_ids = {row["native_entry_id"] for row in inventory["candidates"]}
    assert f"legacy:mnemic:stream-a:2:{'2' * 64}" in native_ids
    assert f"legacy:mnemic:stream-a:3:{'3' * 64}" not in native_ids
    assert f"legacy:mnemic:stream-a:4:{'4' * 64}" in native_ids


def test_import_commit_binds_the_exact_source_file_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "session.jsonl"
    _omp_session(source)
    importer = CassiPiLegacyImporter(object(), tmp_path / "owner")
    preview = _preview(importer, "omp-session", source)
    source.write_text(
        source.read_text(encoding="utf-8")
        + '{"type":"title","title":"metadata outside the imported record set"}\n',
        encoding="utf-8",
    )

    with pytest.raises(CassiPiImportError) as error:
        importer.commit(
            {
                "schema": "cassipi.import-commit.v1",
                "preview_id": preview["preview_id"],
                **SCOPE,
            }
        )
    assert error.value.code == "IMPORT_SOURCE_CHANGED"


def test_sqlite_preview_rejects_a_live_wal_instead_of_copying_one_file(
    tmp_path: Path,
) -> None:
    source = tmp_path / "mnemic.db"
    _mnemic(source)
    writer = sqlite3.connect(source)
    try:
        writer.execute("PRAGMA journal_mode = WAL")
        writer.execute(
            "INSERT INTO mnemic_field_events VALUES (?, ?, ?, ?, ?, ?)",
            (
                "stream-a",
                2,
                "1" * 64,
                "2" * 64,
                '{"kind":"source-gap","record":{"content":"gap"}}',
                1_700_000_001_000,
            ),
        )
        writer.commit()
        wal = Path(f"{source}-wal")
        assert wal.exists() and wal.stat().st_size > 0
        with pytest.raises(CassiPiImportError) as error:
            _preview(CassiPiLegacyImporter(object(), tmp_path / "owner"), "mnemic", source)
        assert error.value.code == "IMPORT_LIVE_SQLITE_UNSUPPORTED"
    finally:
        writer.close()


def test_thalamus_preview_rejects_unknown_schema_version(tmp_path: Path) -> None:
    source = tmp_path / "thalamus.db"
    _thalamus(source)
    db = sqlite3.connect(source)
    db.execute("PRAGMA user_version = 99")
    db.close()

    with pytest.raises(CassiPiImportError, match="user_version is unsupported"):
        _preview(CassiPiLegacyImporter(object(), tmp_path / "owner"), "thalamus", source)
