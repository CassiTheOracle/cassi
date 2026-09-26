/**
 * SessionStore — SQLite-backed persistence for CassiCore sessions.
 *
 * Lives at ~/.cassicore/data/sessions.db
 * Keeps session history, config, and metadata across daemon restarts.
 *
 * Schema is intentionally minimal — sessions are append-heavy, read-on-startup.
 * History is stored as JSON; individual messages are NOT normalized rows because
 * session history is always loaded and written as a unit.
 *
 * Pruning: sessions not active within `maxAgeDays` are removed at open().
 */

import fs from 'node:fs'
import path from 'node:path'

import Database from 'better-sqlite3'

import type { ILogger } from '@cassicore/foundation'
import type { Session } from '@cassicore/foundation'
import type { MnemicField } from '@cassicore/mnemic-field'
import type { EngramCreate } from '@cassicore/mnemic-field'
import { getDataDir } from '@cassicore/foundation'


const SCHEMA_VERSION = 2
const DEFAULT_MAX_AGE_DAYS = 1


export interface SessionRow {
  id:             string
  channel_id:     string
  sender_id:      string
  history_json:   string
  config_json:    string
  token_count:    number
  created_at:     number   // Unix ms
  last_active_at: number   // Unix ms
  version:        number   // Optimistic locking counter
}


/**
 * Thrown when a concurrent save conflicts with an in-progress one.
 * Callers should retry with a fresh load.
 */
export class OptimisticLockError extends Error {
  constructor(sessionId: string, expected: number, actual: number) {
    super(`Session ${sessionId}: optimistic lock conflict — expected version ${expected}, got ${actual}`)
    this.name = 'OptimisticLockError'
  }
}


export class SessionStore {
  private db: InstanceType<typeof Database>
  private mnemicField?: MnemicField

  private constructor(
    dbPath: string,
    private logger: ILogger,
  ) {
    this.db = new Database(dbPath)
    this.db.pragma('journal_mode = WAL')
    this.db.pragma('synchronous = NORMAL')
    this.db.pragma('foreign_keys = ON')
    this.db.pragma('busy_timeout = 5000')
    this.migrate()
  }


  static open(logger: ILogger, dataDir?: string, maxAgeDays = DEFAULT_MAX_AGE_DAYS): SessionStore {
    const dir = dataDir ?? getDataDir()
    fs.mkdirSync(dir, { recursive: true })
    const dbPath = path.join(dir, 'system-state.db')
    const store = new SessionStore(dbPath, logger)
    const pruned = store.prune(maxAgeDays)
    if (pruned > 0) logger.info(`pruned ${pruned} stale session(s) (>${maxAgeDays}d inactive)`)
    logger.info(`open — ${dbPath}`)
    return store
  }

  setMnemicField(field: MnemicField): void {
    this.mnemicField = field
  }


  private migrate(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY
      );
    `)

    const row = this.db.prepare('SELECT version FROM schema_version LIMIT 1').get() as { version: number } | undefined
    const current = row?.version ?? 0

    if (current < 1) {
      this.db.exec(`
        CREATE TABLE IF NOT EXISTS sessions (
          id             TEXT PRIMARY KEY,
          channel_id     TEXT NOT NULL,
          sender_id      TEXT NOT NULL,
          history_json   TEXT NOT NULL DEFAULT '[]',
          config_json    TEXT NOT NULL DEFAULT '{}',
          token_count    INTEGER NOT NULL DEFAULT 0,
          created_at     INTEGER NOT NULL,
          last_active_at INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_sender
          ON sessions (channel_id, sender_id);

        CREATE INDEX IF NOT EXISTS idx_sessions_last_active
          ON sessions (last_active_at);

        INSERT INTO schema_version (version) VALUES (1);
      `)
      this.logger.info('schema v1 created')
    }

    if (current < 2) {
      // v2: Add version column for optimistic locking
      this.db.exec(`
        ALTER TABLE sessions ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
      `)
      // Bump schema version
      this.db.prepare('DELETE FROM schema_version').run()
      this.db.prepare('INSERT INTO schema_version (version) VALUES (2)').run()
      this.logger.info('schema v2 applied — added version column for optimistic locking')
    }
  }


  /**
   * Load a session by its UUID. Returns undefined if not found.
   */
  load(sessionId: string): Session | undefined {
    const row = this.db
      .prepare('SELECT * FROM sessions WHERE id = ?')
      .get(sessionId) as SessionRow | undefined

    if (!row) return undefined
    return this.rowToSession(row)
  }

  /**
   * Find the most recently active session for a channel+sender pair.
   * Used by SessionManager.getOrCreate to warm-start on a known key.
   */
  findBySender(channelId: string, senderId: string): Session | undefined {
    const row = this.db
      .prepare(`
        SELECT * FROM sessions
        WHERE channel_id = ? AND sender_id = ?
        ORDER BY last_active_at DESC
        LIMIT 1
      `)
      .get(channelId, senderId) as SessionRow | undefined

    if (!row) return undefined
    return this.rowToSession(row)
  }


  /**
   * Return all sessions, ordered most-recently-active first.
   * Used by SessionManager.list() to merge disk sessions with the in-memory map.
   */
  listAll(): Session[] {
    const rows = this.db
      .prepare("SELECT * FROM sessions ORDER BY last_active_at DESC")
      .all() as SessionRow[]
    return rows.map(r => this.rowToSession(r))
  }


  /**
   * Upsert a session. Called after every turn completion.
   * Uses optimistic locking: version is auto-incremented on each write.
   */
  save(session: Session): void {
    this.db
      .prepare(`
        INSERT INTO sessions
          (id, channel_id, sender_id, history_json, config_json, token_count, created_at, last_active_at, version)
        VALUES
          (@id, @channel_id, @sender_id, @history_json, @config_json, @token_count, @created_at, @last_active_at, 1)
        ON CONFLICT(id) DO UPDATE SET
          history_json   = excluded.history_json,
          config_json    = excluded.config_json,
          token_count    = excluded.token_count,
          last_active_at = excluded.last_active_at,
          version        = sessions.version + 1
      `)
      .run({
        id:             session.id,
        channel_id:     session.channelId,
        sender_id:      session.senderId,
        history_json:   JSON.stringify(session.history),
        config_json:    JSON.stringify(session.config),
        token_count:    session.tokenCount,
        created_at:     session.createdAt.getTime(),
        last_active_at: session.lastActiveAt.getTime(),
      })
    this.writeReplayEngrams(session)
  }

  /**
   * Save with optimistic locking — only succeeds if the current version matches `expectedVersion`.
   * On conflict, throws `OptimisticLockError`. Caller should reload and retry.
   */
  saveIfVersion(session: Session, expectedVersion: number): number {
    const result = this.db
      .prepare(`
        UPDATE sessions SET
          history_json   = @history_json,
          config_json    = @config_json,
          token_count    = @token_count,
          last_active_at = @last_active_at,
          version        = version + 1
        WHERE id = @id AND version = @expected_version
      `)
      .run({
        id:               session.id,
        history_json:     JSON.stringify(session.history),
        config_json:      JSON.stringify(session.config),
        token_count:      session.tokenCount,
        last_active_at:   session.lastActiveAt.getTime(),
        expected_version: expectedVersion,
      })

    if (result.changes === 0) {
      // Check if row exists to distinguish "not found" from "version conflict"
      const row = this.db.prepare('SELECT version FROM sessions WHERE id = ?').get(session.id) as { version: number } | undefined
      if (row) {
        throw new OptimisticLockError(session.id, expectedVersion, row.version)
      }
      // Row doesn't exist — insert with version 1
      this.save(session)
      return 1
    }

    return expectedVersion + 1
  }

  /**
   * Get the current version of a session (for callers who need to check-then-save).
   */
  getVersion(sessionId: string): number | undefined {
    const row = this.db.prepare('SELECT version FROM sessions WHERE id = ?').get(sessionId) as { version: number } | undefined
    return row?.version
  }

  /**
   * Remove a session by ID.
   */
  remove(sessionId: string): void {
    this.db.prepare('DELETE FROM sessions WHERE id = ?').run(sessionId)
  }


  /**
   * Delete sessions inactive for more than `maxAgeDays`. Returns count removed.
   * Sessions with `config.permanent = true` are never pruned.
   */
  prune(maxAgeDays: number): number {
    const cutoff = Date.now() - maxAgeDays * 24 * 60 * 60 * 1000
    const result = this.db
      .prepare(
        "DELETE FROM sessions WHERE last_active_at < ? AND (config_json NOT LIKE '%\"permanent\":true%')",
      )
      .run(cutoff)
    return result.changes
  }

  /**
   * Delete ALL sessions. Returns count removed.
   */
  pruneAll(): number {
    const result = this.db.prepare('DELETE FROM sessions').run()
    return result.changes
  }

  /**
   * Delete all sessions for a given channelId. Returns count removed.
   */
  pruneByChannelId(channelId: string): number {
    const result = this.db
      .prepare('DELETE FROM sessions WHERE channel_id = ?')
      .run(channelId)
    return result.changes
  }

  /**
   * Delete sessions with an empty history array. Returns count removed.
   */
  pruneEmpty(): number {
    const result = this.db
      .prepare("DELETE FROM sessions WHERE history_json = '[]' OR history_json = ''")
      .run()
    return result.changes
  }


  private rowToSession(row: SessionRow): Session & { _version: number } {
    let history: unknown[];
    let config: Record<string, unknown>;
    try { history = JSON.parse(row.history_json); } catch { history = []; }
    try { config = JSON.parse(row.config_json); } catch { config = {}; }
    return {
      id:           row.id,
      channelId:    row.channel_id,
      senderId:     row.sender_id,
      history:      history as any,
      config:       config as any,
      tokenCount:   row.token_count,
      createdAt:    new Date(row.created_at),
      lastActiveAt: new Date(row.last_active_at),
      _version:     row.version ?? 1,
    }
  }

  private writeReplayEngrams(session: Session): void {
    if (!this.mnemicField) return
    try {
      const sessionId = `session:${session.id}`
      this.upsertReplayEngram({
        id: sessionId,
        content: JSON.stringify({
          channelId: session.channelId,
          senderId: session.senderId,
          startedAt: session.createdAt.toISOString(),
          lastActiveAt: session.lastActiveAt.toISOString(),
          config: session.config,
        }),
        nodeType: 'session',
        t: session.createdAt.getTime(),
        createdAt: session.createdAt.toISOString(),
        tags: ['session-replay', session.channelId],
        provenance: 'session-store',
        metadata: {
          sessionId: session.id,
          channelId: session.channelId,
          senderId: session.senderId,
          tokenCount: session.tokenCount,
        },
      })

      let previousTurnId: string | undefined
      const liveTurnIds = new Set<string>()
      for (let index = 0; index < session.history.length; index++) {
        const message = session.history[index]
        const turnId = `turn:${session.id}:${index + 1}`
        liveTurnIds.add(turnId)
        this.upsertReplayEngram({
          id: turnId,
          content: JSON.stringify({
            role: message.role,
            content: message.content,
            index,
          }),
          nodeType: 'episode',
          t: session.createdAt.getTime() + index + 1,
          createdAt: new Date(session.createdAt.getTime() + index + 1).toISOString(),
          tags: ['session-replay', 'turn', message.role],
          provenance: 'session-store',
          metadata: {
            sessionId: session.id,
            role: message.role,
            index,
          },
        })
        this.mnemicField.connect({ sourceId: turnId, targetId: sessionId, edgeType: 'part_of' })
        if (previousTurnId) {
          this.mnemicField.connect({ sourceId: previousTurnId, targetId: turnId, edgeType: 'temporal_neighbor' })
        }
        previousTurnId = turnId
      }
      for (const oldTurn of this.mnemicField.getEngramsByIdPrefix(`turn:${session.id}:`, { limit: 10_000 })) {
        if (!liveTurnIds.has(oldTurn.id)) this.mnemicField.delete(oldTurn.id)
      }
    } catch (err) {
      this.logger.warn('SessionStore replay engram write failed', { sessionId: session.id, error: String(err) })
    }
  }

  private upsertReplayEngram(input: EngramCreate): void {
    if (!this.mnemicField || !input.id) return
    const existing = this.mnemicField.get(input.id)
    if (existing) {
      this.mnemicField.update(input.id, {
        content: input.content,
        nodeType: input.nodeType,
        x: input.x,
        y: input.y,
        t: input.t,
        potentiation: input.initialPotentiation,
        embedding: input.embedding,
        tags: input.tags,
        metadata: input.metadata,
      })
      return
    }
    this.mnemicField.store(input)
  }

  close(): void {
    this.db.close()
  }
}
