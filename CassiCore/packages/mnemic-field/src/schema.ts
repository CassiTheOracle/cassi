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

    CREATE INDEX IF NOT EXISTS idx_engrams_cluster ON engrams(cluster_id);
    CREATE INDEX IF NOT EXISTS idx_engrams_type ON engrams(node_type);
    CREATE INDEX IF NOT EXISTS idx_engrams_potentiation ON engrams(potentiation DESC);
    CREATE INDEX IF NOT EXISTS idx_engrams_t ON engrams(t);
    CREATE INDEX IF NOT EXISTS idx_synapses_target ON mnemic_synapses(target_id, edge_type);
    CREATE INDEX IF NOT EXISTS idx_synapses_source ON mnemic_synapses(source_id, edge_type);
    CREATE INDEX IF NOT EXISTS idx_spikes_engram ON activation_spikes(engram_id, timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_spikes_timestamp ON activation_spikes(timestamp DESC);
  `)

  createRtreeIfNeeded(db)
  createFtsIfNeeded(db)
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
