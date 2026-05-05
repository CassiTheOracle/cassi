/**
 * HelixSessionStore — Periodic snapshots of brain-integrated Helix state.
 *
 * The journal stores every event. The session store stores point-in-time
 * snapshots so a crash can resume without replaying the full firehose.
 * Snapshots are JSON blobs keyed by session id; the last snapshot for a
 * session wins. Resume loads the snapshot then replays journal entries
 * with `seq > snapshot.seq`.
 *
 * Phase B scope: save/load + simple retention by age. Resume orchestration
 * lives in HelixConductor. The richer snapshot payloads (HelixLocus state,
 * Unity dialectic cursors, etc.) get added in their respective phases.
 */

import fs from 'node:fs'
import path from 'node:path'
import Database from 'better-sqlite3'

import type { ILogger } from '../../../types/interfaces.js'
import { getDataDir } from '../../utils/paths.js'


const SCHEMA_VERSION = 1


export interface HelixSnapshotState {
  /** Monotonic seq from the journal at snapshot time (resume starts from seq+1). */
  seq: number
  /** Active posture module names at this instant. */
  postures: Array<{
    name: string
    role: string
    roleId: string
    submitted: number
    ignited: number
    queued: number
  }>
  /** Telemetry counter snapshot. */
  metrics: Record<string, unknown>
  /** Pending correlations keyed by id (for trace resume). */
  correlationTrace?: Record<string, { seenAt: string; postureId?: string }>
  /** Conductor lifecycle position. */
  conductor: {
    startedAt: string
    lastActivityAt: string
    status: 'running' | 'terminated'
  }
  /** Implementation-defined extra fields (future phases extend this). */
  extra?: Record<string, unknown>
}


export interface HelixSnapshot {
  sessionId: string
  timestamp: string
  state: HelixSnapshotState
}


const SCHEMA_SQL = `
  CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);

  CREATE TABLE IF NOT EXISTS helix_snapshots (
    session_id TEXT PRIMARY KEY,
    timestamp  TEXT NOT NULL,
    seq        INTEGER NOT NULL,
    state_json TEXT NOT NULL
  );

  CREATE INDEX IF NOT EXISTS idx_helix_snapshots_ts ON helix_snapshots(timestamp);
`


export interface HelixSessionStoreOpts {
  logger: ILogger
  dbPath?: string
  inMemory?: boolean
}


export class HelixSessionStore {
  private db: InstanceType<typeof Database>
  private logger: ILogger
  private dbPath: string

  private upsertStmt: Database.Statement
  private selectStmt: Database.Statement
  private listStmt: Database.Statement
  private deleteStmt: Database.Statement
  private pruneStmt: Database.Statement


  constructor(opts: HelixSessionStoreOpts) {
    this.logger = opts.logger.child
      ? opts.logger.child('helix-session-store')
      : opts.logger

    if (opts.dbPath) {
      this.dbPath = opts.dbPath
      fs.mkdirSync(path.dirname(opts.dbPath), { recursive: true })
    } else if (opts.inMemory) {
      this.dbPath = ':memory:'
    } else {
      const dir = getDataDir()
      fs.mkdirSync(dir, { recursive: true })
      this.dbPath = path.join(dir, 'constellation.db')
    }

    this.db = new Database(this.dbPath)
    if (this.dbPath !== ':memory:') {
      this.db.pragma('journal_mode = WAL')
      this.db.pragma('synchronous = NORMAL')
    }
    this.db.pragma('busy_timeout = 5000')

    this.migrate()

    this.upsertStmt = this.db.prepare(
      `INSERT INTO helix_snapshots (session_id, timestamp, seq, state_json)
       VALUES (@sessionId, @timestamp, @seq, @stateJson)
       ON CONFLICT(session_id) DO UPDATE SET
         timestamp = excluded.timestamp,
         seq = excluded.seq,
         state_json = excluded.state_json`,
    )
    this.selectStmt = this.db.prepare(
      `SELECT session_id, timestamp, seq, state_json FROM helix_snapshots WHERE session_id = ?`,
    )
    this.listStmt = this.db.prepare(
      `SELECT session_id, timestamp, seq FROM helix_snapshots ORDER BY timestamp DESC LIMIT ?`,
    )
    this.deleteStmt = this.db.prepare(
      `DELETE FROM helix_snapshots WHERE session_id = ?`,
    )
    this.pruneStmt = this.db.prepare(
      `DELETE FROM helix_snapshots WHERE timestamp < ?`,
    )
  }


  saveSnapshot(sessionId: string, state: HelixSnapshotState): HelixSnapshot {
    const snapshot: HelixSnapshot = {
      sessionId,
      timestamp: new Date().toISOString(),
      state,
    }
    try {
      this.upsertStmt.run({
        sessionId: snapshot.sessionId,
        timestamp: snapshot.timestamp,
        seq: state.seq,
        stateJson: JSON.stringify(state),
      })
    } catch (err) {
      this.logger.warn('snapshot save failed', { error: String(err), sessionId })
      throw err
    }
    return snapshot
  }


  loadSnapshot(sessionId: string): HelixSnapshot | undefined {
    const row = this.selectStmt.get(sessionId) as any
    if (!row) return undefined
    try {
      return {
        sessionId: row.session_id,
        timestamp: row.timestamp,
        state: JSON.parse(row.state_json),
      }
    } catch (err) {
      this.logger.warn('snapshot parse failed', { error: String(err), sessionId })
      return undefined
    }
  }


  listSnapshots(limit = 50): Array<{ sessionId: string; timestamp: string; seq: number }> {
    const rows = this.listStmt.all(limit) as any[]
    return rows.map(r => ({ sessionId: r.session_id, timestamp: r.timestamp, seq: r.seq }))
  }


  deleteSnapshot(sessionId: string): number {
    const result = this.deleteStmt.run(sessionId)
    return result.changes
  }


  pruneOlderThan(cutoff: Date): number {
    const result = this.pruneStmt.run(cutoff.toISOString())
    return result.changes
  }


  close(): void {
    try { this.db.close() } catch (err) {
      this.logger.warn('session-store close failed', { error: String(err) })
    }
  }


  getDbPath(): string {
    return this.dbPath
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


let _sharedSessionStore: HelixSessionStore | undefined

export function getSharedHelixSessionStore(logger: ILogger): HelixSessionStore {
  if (!_sharedSessionStore) {
    _sharedSessionStore = new HelixSessionStore({ logger })
  }
  return _sharedSessionStore
}

export function _resetSharedHelixSessionStoreForTests(): void {
  if (_sharedSessionStore) {
    try { _sharedSessionStore.close() } catch { /* best-effort */ }
    _sharedSessionStore = undefined
  }
}
