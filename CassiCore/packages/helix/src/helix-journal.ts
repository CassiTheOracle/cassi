/**
 * HelixJournal — Append-only SQLite log of Helix session events.
 *
 * The journal is the authoritative per-event record for a brain-integrated
 * Helix session. Every signal submission, workspace ignition, kindling,
 * engram write, Aurora observation, Pineal reinforcement, posture lifecycle
 * transition, and termination decision gets a row.
 *
 * Mnemic Field stores the distilled (milestone-level) summary; this journal
 * stores the full firehose for replay, crash recovery, observability, and
 * training-data ingestion.
 *
 * Schema follows the existing helix-store pattern: one DB file
 * (`~/.cassicore/data/helix-journal.db`), WAL mode, JSON blobs for
 * payloads, a small `schema_version` table for migrations.
 */

import fs from 'node:fs'
import path from 'node:path'
import Database from 'better-sqlite3'

import type { ILogger } from '../../../types/interfaces.js'
import { getDataDir } from '../../utils/paths.js'


const SCHEMA_VERSION = 1


export type HelixJournalEventType =
  | 'session.start'
  | 'session.terminate'
  | 'posture.lifecycle'
  | 'signal.submit'
  | 'signal.ignite'
  | 'workspace.broadcast'
  | 'kindle.spark'
  | 'kindle.radiate'
  | 'engram.write'
  | 'aurora.observe'
  | 'pineal.reinforce'
  | 'snapshot.taken'
  | 'diagnostic'


export interface HelixJournalEntry {
  sessionId: string
  seq: number
  timestamp: string
  eventType: HelixJournalEventType
  postureId?: string
  correlationId?: string
  payload: Record<string, unknown>
}


export interface HelixJournalAppend {
  sessionId: string
  eventType: HelixJournalEventType
  postureId?: string
  correlationId?: string
  payload?: Record<string, unknown>
}


export type JournalSubscriber = (entry: HelixJournalEntry) => void


const SCHEMA_SQL = `
  CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);

  CREATE TABLE IF NOT EXISTS helix_journal (
    session_id     TEXT NOT NULL,
    seq            INTEGER NOT NULL,
    timestamp      TEXT NOT NULL,
    event_type     TEXT NOT NULL,
    posture_id     TEXT,
    correlation_id TEXT,
    payload        TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (session_id, seq)
  );

  CREATE INDEX IF NOT EXISTS idx_helix_journal_correlation
    ON helix_journal(correlation_id);
  CREATE INDEX IF NOT EXISTS idx_helix_journal_type_ts
    ON helix_journal(event_type, timestamp);
  CREATE INDEX IF NOT EXISTS idx_helix_journal_session_ts
    ON helix_journal(session_id, timestamp);
`


export interface HelixJournalOpts {
  logger: ILogger
  /** Override the DB path. Defaults to ~/.cassicore/data/helix-journal.db. */
  dbPath?: string
  /** In-memory only (for tests). Ignored when dbPath is set. */
  inMemory?: boolean
}


export class HelixJournal {
  private db: InstanceType<typeof Database>
  private logger: ILogger
  private dbPath: string
  private subscribers = new Set<JournalSubscriber>()
  private sessionSequences = new Map<string, number>()

  private insertStmt: Database.Statement
  private selectBySessionStmt: Database.Statement
  private selectByCorrelationStmt: Database.Statement
  private selectSessionsStmt: Database.Statement
  private selectLastSeqStmt: Database.Statement
  private countBySessionStmt: Database.Statement
  private deleteSessionStmt: Database.Statement

  constructor(opts: HelixJournalOpts) {
    this.logger = opts.logger.child
      ? opts.logger.child('helix-journal')
      : opts.logger

    if (opts.dbPath) {
      this.dbPath = opts.dbPath
      fs.mkdirSync(path.dirname(opts.dbPath), { recursive: true })
    } else if (opts.inMemory) {
      this.dbPath = ':memory:'
    } else {
      const dir = getDataDir()
      fs.mkdirSync(dir, { recursive: true })
      this.dbPath = path.join(dir, 'helix-journal.db')
    }

    this.db = new Database(this.dbPath)
    if (this.dbPath !== ':memory:') {
      this.db.pragma('journal_mode = WAL')
      this.db.pragma('synchronous = NORMAL')
    }
    this.db.pragma('busy_timeout = 5000')

    this.migrate()

    this.insertStmt = this.db.prepare(
      `INSERT INTO helix_journal (session_id, seq, timestamp, event_type, posture_id, correlation_id, payload)
       VALUES (@sessionId, @seq, @timestamp, @eventType, @postureId, @correlationId, @payload)`,
    )
    this.selectBySessionStmt = this.db.prepare(
      `SELECT * FROM helix_journal WHERE session_id = ? AND seq > ? ORDER BY seq ASC LIMIT ?`,
    )
    this.selectByCorrelationStmt = this.db.prepare(
      `SELECT * FROM helix_journal WHERE correlation_id = ? ORDER BY timestamp ASC LIMIT ?`,
    )
    this.selectSessionsStmt = this.db.prepare(
      `SELECT session_id, MIN(timestamp) as started_at, MAX(timestamp) as last_event_at, COUNT(*) as event_count
       FROM helix_journal
       GROUP BY session_id
       ORDER BY MAX(timestamp) DESC
       LIMIT ?`,
    )
    this.selectLastSeqStmt = this.db.prepare(
      `SELECT MAX(seq) as maxSeq FROM helix_journal WHERE session_id = ?`,
    )
    this.countBySessionStmt = this.db.prepare(
      `SELECT COUNT(*) as count FROM helix_journal WHERE session_id = ?`,
    )
    this.deleteSessionStmt = this.db.prepare(
      `DELETE FROM helix_journal WHERE session_id = ?`,
    )
  }


  /**
   * Append an entry to the journal. Assigns the next monotonic sequence
   * number for the session. Synchronously visible to subsequent reads.
   */
  append(input: HelixJournalAppend): HelixJournalEntry {
    const seq = (this.sessionSequences.get(input.sessionId) ?? this.lookupLastSeq(input.sessionId)) + 1
    const entry: HelixJournalEntry = {
      sessionId: input.sessionId,
      seq,
      timestamp: new Date().toISOString(),
      eventType: input.eventType,
      postureId: input.postureId,
      correlationId: input.correlationId,
      payload: input.payload ?? {},
    }

    try {
      this.insertStmt.run({
        sessionId: entry.sessionId,
        seq: entry.seq,
        timestamp: entry.timestamp,
        eventType: entry.eventType,
        postureId: entry.postureId ?? null,
        correlationId: entry.correlationId ?? null,
        payload: JSON.stringify(entry.payload),
      })
      this.sessionSequences.set(input.sessionId, seq)
    } catch (err) {
      this.logger.warn('journal append failed', {
        error: String(err),
        sessionId: entry.sessionId,
        eventType: entry.eventType,
      })
      throw err
    }

    for (const sub of this.subscribers) {
      try { sub(entry) } catch { /* best-effort */ }
    }

    return entry
  }


  /**
   * Subscribe to new journal entries. Returns an unsubscribe function.
   * Used by the SSE endpoint to push events to clients in real time.
   */
  subscribe(subscriber: JournalSubscriber): () => void {
    this.subscribers.add(subscriber)
    return () => { this.subscribers.delete(subscriber) }
  }


  readSession(sessionId: string, opts: { sinceSeq?: number; limit?: number } = {}): HelixJournalEntry[] {
    const rows = this.selectBySessionStmt.all(sessionId, opts.sinceSeq ?? -1, opts.limit ?? 5_000) as any[]
    return rows.map(rowToEntry)
  }


  readByCorrelation(correlationId: string, limit = 500): HelixJournalEntry[] {
    const rows = this.selectByCorrelationStmt.all(correlationId, limit) as any[]
    return rows.map(rowToEntry)
  }


  listSessions(limit = 50): Array<{
    sessionId: string
    startedAt: string
    lastEventAt: string
    eventCount: number
  }> {
    const rows = this.selectSessionsStmt.all(limit) as any[]
    return rows.map(r => ({
      sessionId: r.session_id,
      startedAt: r.started_at,
      lastEventAt: r.last_event_at,
      eventCount: r.event_count,
    }))
  }


  countSession(sessionId: string): number {
    const row = this.countBySessionStmt.get(sessionId) as any
    return row?.count ?? 0
  }


  deleteSession(sessionId: string): number {
    const result = this.deleteSessionStmt.run(sessionId)
    this.sessionSequences.delete(sessionId)
    return result.changes
  }


  close(): void {
    this.subscribers.clear()
    try {
      this.db.close()
    } catch (err) {
      this.logger.warn('journal close failed', { error: String(err) })
    }
  }


  getDbPath(): string {
    return this.dbPath
  }


  private lookupLastSeq(sessionId: string): number {
    const row = this.selectLastSeqStmt.get(sessionId) as any
    const max = row?.maxSeq
    return typeof max === 'number' ? max : 0
  }


  private migrate(): void {
    this.db.exec(SCHEMA_SQL)
    const row = this.db.prepare(`SELECT MAX(version) as v FROM schema_version`).get() as any
    const current: number = row?.v ?? 0
    if (current < SCHEMA_VERSION) {
      const stmt = this.db.prepare(`INSERT OR REPLACE INTO schema_version (version) VALUES (?)`)
      stmt.run(SCHEMA_VERSION)
    }
  }
}


function rowToEntry(row: any): HelixJournalEntry {
  let payload: Record<string, unknown> = {}
  try { payload = JSON.parse(row.payload ?? '{}') } catch { /* keep empty */ }
  return {
    sessionId: row.session_id,
    seq: row.seq,
    timestamp: row.timestamp,
    eventType: row.event_type,
    postureId: row.posture_id ?? undefined,
    correlationId: row.correlation_id ?? undefined,
    payload,
  }
}


/**
 * Shared process-wide journal singleton — used by both the HelixConductor
 * (writer) and the admin API (reader + subscriber). Lazy so tests that
 * construct their own journals aren't affected.
 */
let _sharedJournal: HelixJournal | undefined

export function getSharedHelixJournal(logger: ILogger): HelixJournal {
  if (!_sharedJournal) {
    _sharedJournal = new HelixJournal({ logger })
  }
  return _sharedJournal
}

/** Test helper — clears the cached singleton. Not used in production. */
export function _resetSharedHelixJournalForTests(): void {
  if (_sharedJournal) {
    try { _sharedJournal.close() } catch { /* best-effort */ }
    _sharedJournal = undefined
  }
}
