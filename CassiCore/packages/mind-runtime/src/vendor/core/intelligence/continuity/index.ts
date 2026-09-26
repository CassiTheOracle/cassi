/**
 * ContinuityModule — Conversation Turn Persistence
 * 
 * - Persists conversation turns to SQLite
 * - Exposes retrieval, FTS search, and pruning
 * - Integrates with BaseCognitiveModule for standardized lifecycle
 * 
 * FIX: Use process.env.HOME (with os.homedir() as fallback) instead of
 * hardcoding homedir() at construction time. homedir() is cached by Node at
 * import time and ignores HOME overrides in tests — this caused getRecent()
 * to always open a *different* DB file than the one saveTurn() wrote to,
 * making recall return an empty array in every test.
 */

import { mkdirSync } from 'fs';
import { join, dirname } from 'path';

import Database from 'better-sqlite3';

import { BaseCognitiveModule } from '../base/cognitive-module.js';
import { getEmbeddingService } from '@cassicore/embeddings';

import type { IContinuity, ConversationTurn } from '@cassicore/foundation';
import type { ILogger } from '@cassicore/foundation';

export class ContinuityModule extends BaseCognitiveModule implements IContinuity {
  readonly name = 'continuity';
  readonly priority = 90;
  
  private db: Database.Database;

  constructor(logger: ILogger) {
    super(logger);
    this.logger = logger.child?.('continuity') ?? logger;

    // Resolve home at construction time so tests can override process.env.HOME
    // before calling new ContinuityModule().
    const home = process.env.HOME ?? require('os').homedir();
    const dbPath = join(home, '.cassicore', 'data', 'system-state.db');

    try {
      mkdirSync(dirname(dbPath), { recursive: true });
    } catch (err) {
      this.logger.warn(`failed to ensure db dir: ${String(err)}`);
    }

    this.db = new Database(dbPath);
    this.db.pragma('busy_timeout = 5000');
    this.initSchema();
  }

  async init(): Promise<void> {
    await super.init();
    this.logger.info('ContinuityModule: initialized', { dbPath: this.db.name });
  }

  /** Initialize tables and FTS virtual table */
  private initSchema(): void {
    this.db.exec(`
      PRAGMA journal_mode=WAL;

      CREATE TABLE IF NOT EXISTS turns (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        tokens_used INTEGER,
        model TEXT,
        timestamp INTEGER NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_session ON turns(session_id, timestamp DESC);
    `);

    try {
      this.db.exec(
        `CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts USING fts5(id UNINDEXED, content, content='turns', content_rowid='rowid');`
      );
    } catch (err) {
      this.logger.warn('FTS5 virtual table creation failed — searchHistory will be limited');
    }
  }

  /** Save a conversation turn */
  async saveTurn(turn: Omit<ConversationTurn, 'id' | 'timestamp'>): Promise<void> {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    const ts = Date.now();
    const stmt = this.db.prepare(
      `INSERT INTO turns (id, session_id, role, content, tokens_used, model, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)`
    );
    try {
      stmt.run(id, turn.sessionId, turn.role, turn.content, turn.tokensUsed ?? null, turn.model ?? null, ts);
      try {
        const fts = this.db.prepare(`INSERT INTO turns_fts(rowid, id, content) VALUES (last_insert_rowid(), ?, ?)`);
        fts.run(id, turn.content);
      } catch (_e) {
        // ignore fts errors
      }
    } catch (err) {
      this.logger.error(`saveTurn failed: ${String(err)}`);
    }
  }

  /**
   * Get recent turns for a session.
   * Returns turns in ascending chronological order (oldest first, newest last)
   * so the model reads history in the correct sequence.
   */
  async getRecent(sessionId: string, limit = 20): Promise<ConversationTurn[]> {
    // Fetch DESC (newest first) then reverse — gives us the N most recent turns
    // in the correct chronological order for prompt injection.
    const stmt = this.db.prepare(`
      SELECT id, session_id, role, content, tokens_used as tokensUse, model, timestamp
      FROM turns
      WHERE session_id = ?
      ORDER BY timestamp DESC
      LIMIT ?
    `);
    try {
      const rows = stmt.all(sessionId, limit) as Array<any>;
      // Reverse so oldest turn comes first — correct reading order for the model
      return rows.reverse().map(r => ({
        id: r.id,
        sessionId: r.session_id,
        role: r.role,
        content: r.content,
        tokensUsed: r.tokensUse ?? undefined,
        model: r.model ?? undefined,
        timestamp: new Date(r.timestamp),
      }));
    } catch (err) {
      this.logger.error(`getRecent failed: ${String(err)}`);
      return [];
    }
  }

  /** Search conversation history: FTS5 recall → embedding re-scoring. */
  async searchHistory(query: string, limit = 10): Promise<ConversationTurn[]> {
    if (!query || query.trim().length === 0) return [];

    // Stage 1: FTS5 broad recall (over-fetch for re-scoring)
    const recallLimit = Math.max(limit * 4, 20);
    let ftsRows: Array<any> = [];
    try {
      const ftsStmt = this.db.prepare(`
        SELECT turns.id, turns.session_id, turns.role, turns.content,
               turns.tokens_used as tokensUse, turns.model, turns.timestamp
        FROM turns
        JOIN turns_fts ON turns.rowid = turns_fts.rowid
        WHERE turns_fts MATCH ?
        ORDER BY rank
        LIMIT ?
      `);
      ftsRows = ftsStmt.all(`${query  }*`, recallLimit) as Array<any>;
    } catch (_err) {
      // fallthrough to LIKE
    }

    if (ftsRows.length === 0) {
      try {
        const like = `%${query.replace(/%/g, '\%')}%`;
        const stmt = this.db.prepare(`
          SELECT id, session_id, role, content, tokens_used as tokensUse, model, timestamp
          FROM turns
          WHERE content LIKE ?
          ORDER BY timestamp DESC
          LIMIT ?
        `);
        ftsRows = stmt.all(like, recallLimit) as Array<any>;
      } catch (err) {
        this.logger.error(`searchHistory failed: ${String(err)}`);
        return [];
      }
    }

    const toTurn = (r: any): ConversationTurn => ({
      id: r.id,
      sessionId: r.session_id,
      role: r.role,
      content: r.content,
      tokensUsed: r.tokensUse ?? undefined,
      model: r.model ?? undefined,
      timestamp: new Date(r.timestamp),
    });

    if (ftsRows.length <= limit) return ftsRows.map(toTurn);

    // Stage 2: Embedding re-scoring (best-effort)
    const embSvc = getEmbeddingService(this.logger);
    if (!embSvc.available) return ftsRows.slice(0, limit).map(toTurn);

    try {
      const queryVec = await embSvc.embed(query, 'query');
      if (!queryVec) return ftsRows.slice(0, limit).map(toTurn);

      const docVecs = await embSvc.embedBatch(
        ftsRows.map(r => (r.content || '').slice(0, 1600)),
        'document',
      );

      const scored = ftsRows.map((r, i) => ({
        row: r,
        score: embSvc.cosineSimilarity(queryVec, docVecs[i]),
      }));
      scored.sort((a, b) => b.score - a.score);
      return scored.slice(0, limit).map(s => toTurn(s.row));
    } catch {
      return ftsRows.slice(0, limit).map(toTurn);
    }
  }

  /** Prune entries older than retentionDays. Returns number deleted. */
  async prune(retentionDays = 180): Promise<number> {
    const cutoff = Date.now() - retentionDays * 24 * 60 * 60 * 1000;
    try {
      const stmt = this.db.prepare(`DELETE FROM turns WHERE timestamp < ?`);
      const info = stmt.run(cutoff);
      try {
        this.db.exec('DELETE FROM turns_fts');
        this.db.exec("INSERT INTO turns_fts(rowid, id, content) SELECT rowid, id, content FROM turns");
      } catch (_e) {
        // ignore
      }
      return info.changes ?? 0;
    } catch (err) {
      this.logger.error(`prune failed: ${String(err)}`);
      return 0;
    }
  }
}

// Keep factory function for backward compatibility
export const createContinuity = (logger: ILogger): ContinuityModule => new ContinuityModule(logger);
