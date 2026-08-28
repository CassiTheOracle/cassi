import type Database from 'better-sqlite3'

export function initForeshadowSchema(db: Database.Database): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS foreshadow_observations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts INTEGER NOT NULL,
      query TEXT NOT NULL,
      query_embedding BLOB,
      embedding_available INTEGER NOT NULL,
      was_cache_hit INTEGER NOT NULL,
      session_id TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_foreshadow_obs_ts ON foreshadow_observations(ts);

    CREATE TABLE IF NOT EXISTS foreshadow_predictions (
      observation_id INTEGER NOT NULL REFERENCES foreshadow_observations(id) ON DELETE CASCADE,
      predictor_id TEXT NOT NULL,
      similarity_to_actual REAL,
      PRIMARY KEY (observation_id, predictor_id)
    );
  `)
}
