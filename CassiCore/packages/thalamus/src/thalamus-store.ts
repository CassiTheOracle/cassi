/**
 * ThalamusStore — SQLite-backed persistence for Thalamus curation audit data.
 *
 * Lives at ~/.cassicore/data/thalamus.db.
 * Persists curation pass metadata and per-message drop/keep records
 * so cassi_context.audit and cassi_context.why survive daemon restarts.
 *
 * Pattern follows HelixStore (core/intelligence/helix/helix-store.ts).
 */

import fs from 'node:fs'
import path from 'node:path'

import Database from 'better-sqlite3'

import type { ILogger } from '../../../types/interfaces.js'
import { getDataDir } from '../../utils/paths.js'
import type { DropRecord } from './types.js'


const SCHEMA_VERSION = 1
const DEFAULT_CLEANUP_AGE_DAYS = 7


export class ThalamusStore {
  private db: InstanceType<typeof Database>

  private constructor(db: InstanceType<typeof Database>, private readonly logger: ILogger) {
    this.db = db
  }

  static open(logger: ILogger, dbPath?: string): ThalamusStore {
    const dir = getDataDir()
    const resolved = dbPath ?? path.join(dir, 'thalamus.db')
    if (!fs.existsSync(path.dirname(resolved))) {
      fs.mkdirSync(path.dirname(resolved), { recursive: true })
    }

    const db = new Database(resolved)
    db.pragma('journal_mode = WAL')
    db.pragma('busy_timeout = 5000')
    db.pragma('synchronous = NORMAL')

    const store = new ThalamusStore(db, logger)
    store.migrate()
    return store
  }

  private migrate(): void {
    const current = (this.db.pragma('user_version') as Array<{ user_version: number }>)[0]?.user_version ?? 0
    if (current >= SCHEMA_VERSION) return

    if (current < 1) {
      this.db.exec(`
        CREATE TABLE IF NOT EXISTS curation_passes (
          id            INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id    TEXT NOT NULL,
          pass_number   INTEGER NOT NULL,
          total_msgs    INTEGER NOT NULL,
          kept_msgs     INTEGER NOT NULL,
          chars_freed   INTEGER NOT NULL,
          threshold     REAL NOT NULL,
          duration_ms   INTEGER,
          created_at    INTEGER NOT NULL DEFAULT (unixepoch())
        );

        CREATE INDEX IF NOT EXISTS idx_passes_session
          ON curation_passes(session_id, pass_number DESC);

        CREATE TABLE IF NOT EXISTS drop_records (
          id            INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id    TEXT NOT NULL,
          pass_number   INTEGER NOT NULL,
          msg_index     INTEGER NOT NULL,
          role          TEXT NOT NULL,
          slot          TEXT NOT NULL DEFAULT 'unknown',
          kept          INTEGER NOT NULL DEFAULT 0,
          pinned        INTEGER NOT NULL DEFAULT 0,
          novelty       REAL NOT NULL DEFAULT 0,
          urgency       REAL NOT NULL DEFAULT 0,
          relevance     REAL NOT NULL DEFAULT 0,
          source_cred   REAL NOT NULL DEFAULT 0,
          composite     REAL NOT NULL DEFAULT 0,
          preview       TEXT,
          created_at    INTEGER NOT NULL DEFAULT (unixepoch())
        );

        CREATE INDEX IF NOT EXISTS idx_drops_session_pass
          ON drop_records(session_id, pass_number DESC);
        CREATE INDEX IF NOT EXISTS idx_drops_session_dropped
          ON drop_records(session_id, kept, composite DESC);

        PRAGMA user_version = 1;
      `)
    }

    this.logger.info('ThalamusStore migrated', { from: current, to: SCHEMA_VERSION })
  }

  /**
   * Record a curation pass and its per-message drop/keep decisions.
   * Called once per curate() invocation.
   */
  recordPass(
    sessionId: string,
    passNumber: number,
    totalMsgs: number,
    keptMsgs: number,
    charsFreed: number,
    threshold: number,
    durationMs: number,
    records: DropRecord[],
  ): void {
    const insertPass = this.db.prepare(`
      INSERT INTO curation_passes (session_id, pass_number, total_msgs, kept_msgs, chars_freed, threshold, duration_ms)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `)

    const insertRecord = this.db.prepare(`
      INSERT INTO drop_records (session_id, pass_number, msg_index, role, slot, kept, pinned,
        novelty, urgency, relevance, source_cred, composite, preview)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `)

    const tx = this.db.transaction(() => {
      insertPass.run(sessionId, passNumber, totalMsgs, keptMsgs, charsFreed, threshold, durationMs)
      for (const r of records) {
        insertRecord.run(
          sessionId, passNumber, r.msgIndex, r.role, r.slot,
          r.kept ? 1 : 0, r.pinned ? 1 : 0,
          r.luminance.novelty, r.luminance.urgency, r.luminance.relevance,
          r.luminance.sourceCredibility, r.luminance.composite,
          r.preview,
        )
      }
    })

    tx()
  }

  /**
   * Return recent curation passes for a session.
   */
  getPasses(sessionId: string, window: number = 5): Array<{
    passNumber: number
    totalMsgs: number
    keptMsgs: number
    charsFreed: number
    threshold: number
    durationMs: number
    createdAt: number
  }> {
    const rows = this.db.prepare(`
      SELECT pass_number, total_msgs, kept_msgs, chars_freed, threshold, duration_ms, created_at
      FROM curation_passes
      WHERE session_id = ?
      ORDER BY pass_number DESC
      LIMIT ?
    `).all(sessionId, window)

    return rows.map((r: any) => ({
      passNumber: r.pass_number,
      totalMsgs: r.total_msgs,
      keptMsgs: r.kept_msgs,
      charsFreed: r.chars_freed,
      threshold: r.threshold,
      durationMs: r.duration_ms,
      createdAt: r.created_at,
    }))
  }

  /**
   * Return drop/keep records for recent passes of a session.
   */
  getDropRecords(sessionId: string, window: number = 5): DropRecord[] {
    const passes = this.getPasses(sessionId, window)
    if (passes.length === 0) return []

    const minPass = passes[passes.length - 1].passNumber
    const rows = this.db.prepare(`
      SELECT pass_number, msg_index, role, slot, kept, pinned,
        novelty, urgency, relevance, source_cred, composite, preview
      FROM drop_records
      WHERE session_id = ? AND pass_number >= ?
      ORDER BY pass_number DESC, msg_index ASC
    `).all(sessionId, minPass)

    return rows.map((r: any) => ({
      curationPass: r.pass_number,
      msgIndex: r.msg_index,
      role: r.role,
      slot: r.slot,
      kept: r.kept === 1,
      pinned: r.pinned === 1,
      luminance: {
        novelty: r.novelty,
        urgency: r.urgency,
        relevance: r.relevance,
        sourceCredibility: r.source_cred,
        composite: r.composite,
      },
      preview: r.preview ?? '',
    }))
  }

  /**
   * Return the luminance breakdown for a specific message in the latest pass.
   */
  getWhy(sessionId: string, msgIndex: number): DropRecord | null {
    const row = this.db.prepare(`
      SELECT pass_number, msg_index, role, slot, kept, pinned,
        novelty, urgency, relevance, source_cred, composite, preview
      FROM drop_records
      WHERE session_id = ? AND msg_index = ?
      ORDER BY pass_number DESC
      LIMIT 1
    `).get(sessionId, msgIndex) as any

    if (!row) return null

    return {
      curationPass: row.pass_number,
      msgIndex: row.msg_index,
      role: row.role,
      slot: row.slot,
      kept: row.kept === 1,
      pinned: row.pinned === 1,
      luminance: {
        novelty: row.novelty,
        urgency: row.urgency,
        relevance: row.relevance,
        sourceCredibility: row.source_cred,
        composite: row.composite,
      },
      preview: row.preview ?? '',
    }
  }

  /**
   * Remove records older than DEFAULT_CLEANUP_AGE_DAYS.
   */
  cleanup(maxAgeDays: number = DEFAULT_CLEANUP_AGE_DAYS): number {
    const cutoff = Math.floor(Date.now() / 1000) - (maxAgeDays * 86400)
    const r1 = this.db.prepare('DELETE FROM drop_records WHERE created_at < ?').run(cutoff)
    const r2 = this.db.prepare('DELETE FROM curation_passes WHERE created_at < ?').run(cutoff)
    const total = r1.changes + r2.changes
    if (total > 0) {
      this.logger.info('ThalamusStore cleanup', { removed: total, maxAgeDays })
    }
    return total
  }

  close(): void {
    this.db.close()
  }
}
