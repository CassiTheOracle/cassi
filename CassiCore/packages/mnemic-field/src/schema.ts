import type Database from 'better-sqlite3'

export function initMnemicFieldSchema(db: Database.Database): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS engrams (
      id TEXT PRIMARY KEY,
      content TEXT NOT NULL,
      node_type TEXT NOT NULL,
      x REAL NOT NULL DEFAULT 0,
      y REAL NOT NULL DEFAULT 0,
      z REAL NOT NULL DEFAULT 0,
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
      centroid_z REAL NOT NULL DEFAULT 0,
      member_count INTEGER NOT NULL DEFAULT 0,
      avg_potentiation REAL NOT NULL DEFAULT 0,
      abstraction_id TEXT,
      parent_nucleus_id TEXT REFERENCES nuclei(id),
      depth INTEGER NOT NULL DEFAULT 0,
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
    CREATE INDEX IF NOT EXISTS idx_replay_part_of_parent ON mnemic_synapses(target_id, edge_type, source_id)
      WHERE edge_type = 'part_of';
    CREATE INDEX IF NOT EXISTS idx_replay_temporal_next ON mnemic_synapses(source_id, edge_type, target_id)
      WHERE edge_type = 'temporal_neighbor';
    CREATE INDEX IF NOT EXISTS idx_replay_temporal_prev ON mnemic_synapses(target_id, edge_type, source_id)
      WHERE edge_type = 'temporal_neighbor';
    CREATE INDEX IF NOT EXISTS idx_replay_caused_by_call ON mnemic_synapses(target_id, edge_type, source_id)
      WHERE edge_type = 'caused_by';
    CREATE INDEX IF NOT EXISTS idx_replay_spawned_from_parent ON mnemic_synapses(target_id, edge_type, source_id)
      WHERE edge_type = 'spawned_from';
    CREATE INDEX IF NOT EXISTS idx_spikes_engram ON activation_spikes(engram_id, timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_spikes_timestamp ON activation_spikes(timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_changesets_status ON changesets(status);
    CREATE INDEX IF NOT EXISTS idx_changesets_committed ON changesets(committed_at DESC);
    CREATE INDEX IF NOT EXISTS idx_changeset_files_engram ON changeset_files(engram_id);

    CREATE VIEW IF NOT EXISTS replay_part_of_edges AS
      SELECT source_id AS child_id, target_id AS parent_id, weight, created_at, metadata
      FROM mnemic_synapses
      WHERE edge_type = 'part_of';

    CREATE VIEW IF NOT EXISTS replay_temporal_edges AS
      SELECT source_id AS previous_id, target_id AS next_id, weight, created_at, metadata
      FROM mnemic_synapses
      WHERE edge_type = 'temporal_neighbor';

    CREATE VIEW IF NOT EXISTS replay_session_nodes AS
      SELECT id, node_type, content, t, created_at, metadata
      FROM engrams
      WHERE id LIKE 'session:%'
         OR id LIKE 'run:%'
         OR id LIKE 'step:%'
         OR id LIKE 'turn:%'
         OR id LIKE 'tc:%'
         OR id LIKE 'tr:%'
         OR id LIKE 'err:%'
         OR id LIKE 'artifact:%';

    -- Neural Kindling: forward traces for backpropagation during consolidation
    CREATE TABLE IF NOT EXISTS forward_traces (
      id TEXT PRIMARY KEY,
      created_at REAL NOT NULL,
      seed_charges TEXT NOT NULL,
      records TEXT NOT NULL,
      output_charges TEXT NOT NULL,
      spark_point REAL NOT NULL,
      luminal_ids TEXT NOT NULL
    );

    -- Neural Kindling: gradient requests from enrichment feedback
    CREATE TABLE IF NOT EXISTS gradient_requests (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      trace_id TEXT NOT NULL REFERENCES forward_traces(id) ON DELETE CASCADE,
      feedback TEXT NOT NULL,
      created_at REAL NOT NULL,
      processed INTEGER NOT NULL DEFAULT 0
    );

    -- Neural Kindling: Adam optimizer state per synapse
    CREATE TABLE IF NOT EXISTS synapse_optimizer_state (
      source_id TEXT NOT NULL,
      target_id TEXT NOT NULL,
      edge_type TEXT NOT NULL,
      m REAL NOT NULL DEFAULT 0,
      v REAL NOT NULL DEFAULT 0,
      step INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY (source_id, target_id, edge_type)
    );

    CREATE INDEX IF NOT EXISTS idx_forward_traces_created ON forward_traces(created_at);
    CREATE INDEX IF NOT EXISTS idx_gradient_requests_processed ON gradient_requests(processed, created_at);
  `)

  createRtreeIfNeeded(db)
  createFtsIfNeeded(db)
  createFilamentsFtsIfNeeded(db)
  createLightningIndexTablesIfNeeded(db)
  createLightningRetrievalEventsTableIfNeeded(db)
  createLightningTrainingRequestsTableIfNeeded(db)
  createIndexerVersionsTableIfNeeded(db)
  createIndexerTrainingStepsTableIfNeeded(db)
  createLightningValidationSetTableIfNeeded(db)
  createReplayInfraIfNeeded(db)
  migrateSchema(db)
}

function createReplayInfraIfNeeded(db: Database.Database): void {
  db.exec(`
    CREATE INDEX IF NOT EXISTS idx_engrams_session_id
      ON engrams (json_extract(metadata, '$.sessionId'))
      WHERE json_extract(metadata, '$.sessionId') IS NOT NULL;

    CREATE INDEX IF NOT EXISTS idx_engrams_parent_message_id
      ON engrams (json_extract(metadata, '$.parentMessageId'))
      WHERE json_extract(metadata, '$.parentMessageId') IS NOT NULL;

    CREATE INDEX IF NOT EXISTS idx_engrams_session_t
      ON engrams (json_extract(metadata, '$.sessionId'), t)
      WHERE json_extract(metadata, '$.sessionId') IS NOT NULL;

    CREATE INDEX IF NOT EXISTS idx_engrams_branch_id
      ON engrams (json_extract(metadata, '$.branchId'))
      WHERE json_extract(metadata, '$.branchId') IS NOT NULL;
  `)
}

function createLightningIndexTablesIfNeeded(db: Database.Database): void {
  const exists = db.prepare(
    `SELECT 1 FROM sqlite_master WHERE type='table' AND name='lightning_index_global'`
  ).get()

  if (!exists) {
    db.exec(`
      CREATE TABLE lightning_index_global (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        w_dq BLOB NOT NULL,
        w_iuq BLOB NOT NULL,
        w_i BLOB NOT NULL,
        d_emb INTEGER NOT NULL,
        d_c INTEGER NOT NULL,
        n_h INTEGER NOT NULL,
        d_idx INTEGER NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL
      );

      CREATE TABLE lightning_index_keys (
        engram_id TEXT PRIMARY KEY,
        keys BLOB NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL
      );

      CREATE INDEX idx_lightning_keys_version ON lightning_index_keys(version);
    `)
  }
}

function createLightningRetrievalEventsTableIfNeeded(db: Database.Database): void {
  const exists = db.prepare(
    `SELECT 1 FROM sqlite_master WHERE type='table' AND name='lightning_retrieval_events'`
  ).get()

  if (!exists) {
    db.exec(`
      CREATE TABLE lightning_retrieval_events (
        retrieval_id TEXT PRIMARY KEY,
        session_id TEXT,
        query_text TEXT NOT NULL,
        query_embedding BLOB,
        candidate_ids TEXT NOT NULL,
        indexer_scores TEXT,
        reranker_scores TEXT,
        indexer_version INTEGER,
        mode TEXT NOT NULL,
        created_at TEXT NOT NULL
      );

      CREATE INDEX idx_lightning_retrieval_session_created
        ON lightning_retrieval_events(session_id, created_at);
      CREATE INDEX idx_lightning_retrieval_created
        ON lightning_retrieval_events(created_at);
      CREATE INDEX idx_lightning_retrieval_mode
        ON lightning_retrieval_events(mode);
    `)
  }
}

function createLightningTrainingRequestsTableIfNeeded(db: Database.Database): void {
  const exists = db.prepare(
    `SELECT 1 FROM sqlite_master WHERE type='table' AND name='lightning_training_requests'`
  ).get()

  if (!exists) {
    db.exec(`
      CREATE TABLE lightning_training_requests (
        retrieval_id TEXT NOT NULL,
        candidate_id TEXT NOT NULL,
        label TEXT NOT NULL CHECK (label IN ('used', 'ignored', 'contradicted', 'should_have_been_retrieved')),
        weight REAL NOT NULL DEFAULT 1.0,
        evidence TEXT NOT NULL DEFAULT '{}',
        indexer_score REAL,
        reranker_score REAL,
        created_at TEXT NOT NULL,
        processed_at TEXT,
        PRIMARY KEY (retrieval_id, candidate_id)
      );

      CREATE INDEX idx_lightning_training_unprocessed
        ON lightning_training_requests(processed_at)
        WHERE processed_at IS NULL;
      CREATE INDEX idx_lightning_training_created
        ON lightning_training_requests(created_at);
      CREATE INDEX idx_lightning_training_label
        ON lightning_training_requests(label, processed_at);
    `)
  }
}

function createIndexerVersionsTableIfNeeded(db: Database.Database): void {
  const exists = db.prepare(
    `SELECT 1 FROM sqlite_master WHERE type='table' AND name='indexer_versions'`
  ).get()
  if (!exists) {
    db.exec(`
      CREATE TABLE indexer_versions (
        version INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_version INTEGER REFERENCES indexer_versions(version),
        weights BLOB NOT NULL,
        d_emb INTEGER NOT NULL,
        d_c INTEGER NOT NULL,
        n_h INTEGER NOT NULL,
        d_idx INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'archived'
          CHECK (status IN ('active', 'archived', 'rolled_back')),
        training_steps INTEGER NOT NULL DEFAULT 0,
        requests_consumed INTEGER NOT NULL DEFAULT 0,
        validation_loss REAL,
        validation_recall_at_5 REAL,
        notes TEXT,
        created_at TEXT NOT NULL
      );
      CREATE UNIQUE INDEX idx_indexer_versions_active
        ON indexer_versions(status) WHERE status = 'active';
      CREATE INDEX idx_indexer_versions_created
        ON indexer_versions(created_at);
    `)
  }
}

function createIndexerTrainingStepsTableIfNeeded(db: Database.Database): void {
  const exists = db.prepare(
    `SELECT 1 FROM sqlite_master WHERE type='table' AND name='indexer_training_steps'`
  ).get()
  if (!exists) {
    db.exec(`
      CREATE TABLE indexer_training_steps (
        step_id INTEGER PRIMARY KEY AUTOINCREMENT,
        version INTEGER NOT NULL REFERENCES indexer_versions(version) ON DELETE CASCADE,
        requests_in_batch INTEGER NOT NULL,
        loss_before REAL,
        loss_after REAL,
        learning_rate REAL NOT NULL,
        muon_momentum REAL,
        muon_steps INTEGER NOT NULL DEFAULT 0,
        adamw_steps INTEGER NOT NULL DEFAULT 0,
        grad_norm REAL,
        duration_ms INTEGER NOT NULL,
        created_at TEXT NOT NULL
      );
      CREATE INDEX idx_indexer_training_steps_version_created
        ON indexer_training_steps(version, created_at);
    `)
  }
}

function createLightningValidationSetTableIfNeeded(db: Database.Database): void {
  const exists = db.prepare(
    `SELECT 1 FROM sqlite_master WHERE type='table' AND name='lightning_validation_set'`
  ).get()
  if (!exists) {
    db.exec(`
      CREATE TABLE lightning_validation_set (
        validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_text TEXT NOT NULL,
        query_embedding BLOB NOT NULL,
        candidate_id TEXT NOT NULL,
        expected_label TEXT NOT NULL CHECK (
          expected_label IN ('used', 'ignored', 'contradicted', 'should_have_been_retrieved')
        ),
        weight REAL NOT NULL DEFAULT 1.0,
        source_retrieval_id TEXT,
        curated_by TEXT NOT NULL DEFAULT 'reverie',
        notes TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        UNIQUE (query_text, candidate_id)
      );
      CREATE INDEX idx_lightning_validation_active
        ON lightning_validation_set(active) WHERE active = 1;
      CREATE INDEX idx_lightning_validation_created
        ON lightning_validation_set(created_at);
    `)
  }
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

  const hasOldTable = db.prepare(`SELECT 1 FROM sqlite_master WHERE type='table' AND name='forward_tapes'`).get()
  if (hasOldTable) {
    db.exec(`ALTER TABLE forward_tapes RENAME TO forward_traces`)
    db.exec(`ALTER TABLE gradient_requests RENAME COLUMN tape_id TO trace_id`)
  }

  remediateMigrationTimestamps(db)
  migrateSessionIdColumn(db)
  migrateExpertIndexes(db)
  migrateFileTrackingColumns(db)
}

function migrateSessionIdColumn(db: Database.Database): void {
  const cols = db.prepare(`PRAGMA table_info(engrams)`).all() as Array<{ name: string }>
  const names = new Set(cols.map(c => c.name))
  if (names.has('session_id')) return

  db.exec(`ALTER TABLE engrams ADD COLUMN session_id TEXT`)

  db.exec(`
    UPDATE engrams
    SET session_id = json_extract(metadata, '$.sessionId')
    WHERE json_extract(metadata, '$.sessionId') IS NOT NULL
  `)

  db.exec(`
    CREATE INDEX IF NOT EXISTS idx_engrams_session_id_col
      ON engrams(session_id)
      WHERE session_id IS NOT NULL;
    CREATE INDEX IF NOT EXISTS idx_engrams_session_t_col
      ON engrams(session_id, t)
      WHERE session_id IS NOT NULL;
  `)
}

function migrateExpertIndexes(db: Database.Database): void {
  db.exec(`
    CREATE INDEX IF NOT EXISTS idx_engrams_expert_kind
      ON engrams(json_extract(metadata, '$.expertKind'))
      WHERE json_extract(metadata, '$.expertKind') IS NOT NULL;

    CREATE INDEX IF NOT EXISTS idx_engrams_expert_domain
      ON engrams(json_extract(metadata, '$.expertDomain'))
      WHERE json_extract(metadata, '$.expertDomain') IS NOT NULL;

    CREATE INDEX IF NOT EXISTS idx_engrams_expert_id
      ON engrams(json_extract(metadata, '$.expertId'))
      WHERE json_extract(metadata, '$.expertId') IS NOT NULL;
  `)
}

function migrateFileTrackingColumns(db: Database.Database): void {
  const cols = db.prepare(`PRAGMA table_info(engrams)`).all() as Array<{ name: string }>
  const names = new Set(cols.map(c => c.name))

  // Add file_path column for fast file-path lookups without json_extract
  if (!names.has('file_path')) {
    db.exec(`ALTER TABLE engrams ADD COLUMN file_path TEXT`)
  }

  // Add content_hash column for dedup and diff computation
  if (!names.has('content_hash')) {
    db.exec(`ALTER TABLE engrams ADD COLUMN content_hash TEXT`)
  }

  // Index on file_path — partial so only file engrams are indexed
  db.exec(`
    CREATE INDEX IF NOT EXISTS idx_engrams_file_path
      ON engrams(file_path)
      WHERE file_path IS NOT NULL
  `)

  // Backfill file_path from metadata.filePath for existing file engrams
  db.prepare(`
    UPDATE engrams
    SET file_path = json_extract(metadata, '$.filePath')
    WHERE node_type = 'file'
      AND file_path IS NULL
      AND json_extract(metadata, '$.filePath') IS NOT NULL
  `).run()

  // Backfill content_hash for file_version engrams — independent of file_path backfill
  db.prepare(`
    UPDATE engrams
    SET content_hash = json_extract(metadata, '$.checksum')
    WHERE node_type = 'file_version'
      AND content_hash IS NULL
      AND json_extract(metadata, '$.checksum') IS NOT NULL
  `).run()
}

function remediateMigrationTimestamps(db: Database.Database): void {
  const affected = db.prepare(`
    SELECT COUNT(*) as cnt FROM engrams
    WHERE created_at LIKE '2026-04-08T14:4%' AND t > 0
  `).get() as { cnt: number }

  if (affected.cnt === 0) return

  db.exec(`BEGIN TRANSACTION`)
  try {
    db.prepare(`
      UPDATE engrams
      SET t = t / 1000,
          created_at = strftime('%Y-%m-%dT%H:%M:%fZ', t / 1000 / 1000, 'unixepoch')
      WHERE created_at LIKE '2026-04-08T14:4%' AND t >= 1e15
    `).run()

    db.prepare(`
      UPDATE engrams
      SET created_at = strftime('%Y-%m-%dT%H:%M:%fZ', t / 1000, 'unixepoch')
      WHERE created_at LIKE '2026-04-08T14:4%' AND t > 0 AND t < 1e15
    `).run()

    const rtreeExists = db.prepare(
      `SELECT 1 FROM sqlite_master WHERE type='table' AND name='engram_rtree'`
    ).get()

    if (rtreeExists) {
      db.prepare(`
        UPDATE engram_rtree
        SET t_min = e.t, t_max = e.t
        FROM engrams e
        WHERE engram_rtree.id = e.rowid
          AND engram_rtree.t_min >= 1e15
      `).run()
    }

    db.exec(`COMMIT`)
  } catch (err) {
    db.exec(`ROLLBACK`)
    throw err
  }
}
