import type Database from 'better-sqlite3'

export function initMnemicFieldSchema(db: Database.Database): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS engrams (
      id TEXT PRIMARY KEY,
      content TEXT NOT NULL,
      node_type TEXT NOT NULL,
      x REAL NOT NULL DEFAULT 0,
      y REAL NOT NULL DEFAULT 0,
      t REAL NOT NULL DEFAULT 0,
      potentiation REAL NOT NULL DEFAULT 0,
      cluster_id TEXT,
      embedding BLOB,
      tags TEXT DEFAULT '[]',
      provenance TEXT DEFAULT '',
      created_at TEXT NOT NULL,
      accessed_at TEXT,
      metadata TEXT DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS mnemic_synapses (
      source_id TEXT NOT NULL REFERENCES engrams(id) ON DELETE CASCADE,
      target_id TEXT NOT NULL REFERENCES engrams(id) ON DELETE CASCADE,
      edge_type TEXT NOT NULL,
      weight REAL NOT NULL DEFAULT 1.0,
      created_at TEXT NOT NULL,
      metadata TEXT DEFAULT '{}',
      PRIMARY KEY (source_id, target_id, edge_type)
    );

    CREATE TABLE IF NOT EXISTS activation_spikes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      engram_id TEXT NOT NULL REFERENCES engrams(id) ON DELETE CASCADE,
      timestamp REAL NOT NULL,
      magnitude REAL NOT NULL,
      task_context TEXT,
      outcome TEXT
    );

    CREATE TABLE IF NOT EXISTS nuclei (
      id TEXT PRIMARY KEY,
      label TEXT NOT NULL DEFAULT '',
      centroid_x REAL NOT NULL DEFAULT 0,
      centroid_y REAL NOT NULL DEFAULT 0,
      member_count INTEGER NOT NULL DEFAULT 0,
      avg_potentiation REAL NOT NULL DEFAULT 0,
      abstraction_id TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS migration_jobs (
      id TEXT PRIMARY KEY,
      status TEXT NOT NULL,
      phase TEXT NOT NULL DEFAULT 'memories',
      source_db_path TEXT NOT NULL,
      migrate_archives INTEGER NOT NULL DEFAULT 0,
      include_archived INTEGER NOT NULL DEFAULT 0,
      infer_synapses INTEGER NOT NULL DEFAULT 1,
      enable_micro_chunking INTEGER NOT NULL DEFAULT 1,
      use_local_embeddings INTEGER NOT NULL DEFAULT 0,
      memory_limit INTEGER,
      archive_limit INTEGER,
      archive_link_limit INTEGER,
      micro_chunk_token_target INTEGER,
      migrated_memories INTEGER NOT NULL DEFAULT 0,
      migrated_archives INTEGER NOT NULL DEFAULT 0,
      created_synapses INTEGER NOT NULL DEFAULT 0,
      created_fragments INTEGER NOT NULL DEFAULT 0,
      next_memory_offset INTEGER NOT NULL DEFAULT 0,
      next_archive_offset INTEGER NOT NULL DEFAULT 0,
      next_link_offset INTEGER NOT NULL DEFAULT 0,
      error_text TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      completed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS changesets (
      id TEXT PRIMARY KEY,
      description TEXT NOT NULL,
      author_session_id TEXT,
      author_agent_id TEXT,
      parent_changeset_id TEXT,
      status TEXT NOT NULL DEFAULT 'pending',
      build_verified INTEGER NOT NULL DEFAULT 0,
      file_count INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL,
      committed_at TEXT,
      metadata TEXT DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS changeset_files (
      changeset_id TEXT NOT NULL REFERENCES changesets(id) ON DELETE CASCADE,
      engram_id TEXT NOT NULL REFERENCES engrams(id) ON DELETE CASCADE,
      previous_checksum TEXT,
      previous_content TEXT,
      operation TEXT NOT NULL,
      PRIMARY KEY (changeset_id, engram_id)
    );

    CREATE INDEX IF NOT EXISTS idx_engrams_cluster ON engrams(cluster_id);
    CREATE INDEX IF NOT EXISTS idx_engrams_type ON engrams(node_type);
    CREATE INDEX IF NOT EXISTS idx_engrams_potentiation ON engrams(potentiation DESC);
    CREATE INDEX IF NOT EXISTS idx_engrams_t ON engrams(t);
    CREATE INDEX IF NOT EXISTS idx_migration_jobs_status ON migration_jobs(status);
    CREATE INDEX IF NOT EXISTS idx_synapses_target ON mnemic_synapses(target_id, edge_type);
    CREATE INDEX IF NOT EXISTS idx_synapses_source ON mnemic_synapses(source_id, edge_type);
    CREATE INDEX IF NOT EXISTS idx_spikes_engram ON activation_spikes(engram_id, timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_spikes_timestamp ON activation_spikes(timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_changesets_status ON changesets(status);
    CREATE INDEX IF NOT EXISTS idx_changesets_committed ON changesets(committed_at DESC);
    CREATE INDEX IF NOT EXISTS idx_changeset_files_engram ON changeset_files(engram_id);

    CREATE TABLE IF NOT EXISTS filaments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      engram_id TEXT NOT NULL REFERENCES engrams(id) ON DELETE CASCADE,
      span_start INTEGER NOT NULL,
      span_end INTEGER NOT NULL,
      content TEXT NOT NULL,
      embedding BLOB,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS filament_synapses (
      source_id INTEGER NOT NULL REFERENCES filaments(id) ON DELETE CASCADE,
      target_id INTEGER NOT NULL REFERENCES filaments(id) ON DELETE CASCADE,
      edge_type TEXT NOT NULL,
      weight REAL NOT NULL DEFAULT 0.5,
      confidence REAL NOT NULL DEFAULT 1.0,
      provenance TEXT NOT NULL,
      created_at TEXT NOT NULL,
      metadata TEXT,
      PRIMARY KEY (source_id, target_id, edge_type)
    );

    CREATE TABLE IF NOT EXISTS filament_entities (
      filament_id INTEGER NOT NULL REFERENCES filaments(id) ON DELETE CASCADE,
      entity TEXT NOT NULL,
      entity_type TEXT NOT NULL,
      PRIMARY KEY (filament_id, entity)
    );

    CREATE TABLE IF NOT EXISTS filament_analysis_log (
      source_id INTEGER NOT NULL,
      target_id INTEGER NOT NULL,
      analyzed_at TEXT NOT NULL,
      PRIMARY KEY (source_id, target_id)
    );

    CREATE INDEX IF NOT EXISTS idx_filaments_engram ON filaments(engram_id);
    CREATE INDEX IF NOT EXISTS idx_filament_syn_source ON filament_synapses(source_id, edge_type);
    CREATE INDEX IF NOT EXISTS idx_filament_syn_target ON filament_synapses(target_id, edge_type);
    CREATE INDEX IF NOT EXISTS idx_fent_entity ON filament_entities(entity);
  `)

  createRtreeIfNeeded(db)
  createFtsIfNeeded(db)
  createFilamentsFtsIfNeeded(db)
  migrateSchema(db)
}

function createRtreeIfNeeded(db: Database.Database): void {
  const rtreeExists = db.prepare(
    `SELECT 1 FROM sqlite_master WHERE type='table' AND name='engram_rtree'`
  ).get()

  if (!rtreeExists) {
    db.exec(`
      CREATE VIRTUAL TABLE engram_rtree USING rtree(
        id,
        x_min, x_max,
        y_min, y_max,
        t_min, t_max,
        potentiation_min, potentiation_max
      );
    `)
  }
}

function createFtsIfNeeded(db: Database.Database): void {
  const ftsExists = db.prepare(
    `SELECT 1 FROM sqlite_master WHERE type='table' AND name='engrams_fts'`
  ).get()

  if (!ftsExists) {
    db.exec(`
      CREATE VIRTUAL TABLE engrams_fts USING fts5(
        content, tags, provenance,
        content='engrams', content_rowid='rowid'
      );
    `)

    db.exec(`
      CREATE TRIGGER IF NOT EXISTS engrams_fts_insert AFTER INSERT ON engrams BEGIN
        INSERT INTO engrams_fts(rowid, content, tags, provenance)
        VALUES (NEW.rowid, NEW.content, NEW.tags, NEW.provenance);
      END;

      CREATE TRIGGER IF NOT EXISTS engrams_fts_delete AFTER DELETE ON engrams BEGIN
        INSERT INTO engrams_fts(engrams_fts, rowid, content, tags, provenance)
        VALUES ('delete', OLD.rowid, OLD.content, OLD.tags, OLD.provenance);
      END;

      CREATE TRIGGER IF NOT EXISTS engrams_fts_update AFTER UPDATE ON engrams BEGIN
        INSERT INTO engrams_fts(engrams_fts, rowid, content, tags, provenance)
        VALUES ('delete', OLD.rowid, OLD.content, OLD.tags, OLD.provenance);
        INSERT INTO engrams_fts(rowid, content, tags, provenance)
        VALUES (NEW.rowid, NEW.content, NEW.tags, NEW.provenance);
      END;
    `)
  }
}

function createFilamentsFtsIfNeeded(db: Database.Database): void {
  const ftsExists = db.prepare(
    `SELECT 1 FROM sqlite_master WHERE type='table' AND name='filaments_fts'`
  ).get()

  if (!ftsExists) {
    db.exec(`
      CREATE VIRTUAL TABLE filaments_fts USING fts5(
        content,
        content='filaments', content_rowid='id'
      );
    `)

    db.exec(`
      CREATE TRIGGER IF NOT EXISTS filaments_fts_insert AFTER INSERT ON filaments BEGIN
        INSERT INTO filaments_fts(rowid, content)
        VALUES (NEW.id, NEW.content);
      END;

      CREATE TRIGGER IF NOT EXISTS filaments_fts_delete AFTER DELETE ON filaments BEGIN
        INSERT INTO filaments_fts(filaments_fts, rowid, content)
        VALUES ('delete', OLD.id, OLD.content);
      END;

      CREATE TRIGGER IF NOT EXISTS filaments_fts_update AFTER UPDATE ON filaments BEGIN
        INSERT INTO filaments_fts(filaments_fts, rowid, content)
        VALUES ('delete', OLD.id, OLD.content);
        INSERT INTO filaments_fts(rowid, content)
        VALUES (NEW.id, NEW.content);
      END;
    `)
  }
}

function migrateSchema(db: Database.Database): void {
  const cols = db.prepare(`PRAGMA table_info(migration_jobs)`).all() as Array<{ name: string }>
  const names = new Set(cols.map(c => c.name))
  if (!names.has('phase')) {
    db.exec(`ALTER TABLE migration_jobs ADD COLUMN phase TEXT NOT NULL DEFAULT 'memories'`)
  }
}
