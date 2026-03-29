/**
 * rate-limit-store.ts — Persistent SQLite store for adaptive rate-limit learned limits.
 *
 * Each CentralizedProvider learns provider/model rate ceilings from 429 responses
 * at three timescale windows (1m, 10m, 1h). Previously those limits were lost on
 * daemon restart, forcing a burn-in period of re-hitting 429s on every boot.
 *
 * This store survives restarts. On startup CentralizedProvider loads its learned
 * limits and immediately enforces them without needing to re-discover them.
 *
 * Storage: ~/.cassicore/data/rate-limits.db
 * One row per (provider_id, model, window_label) — upserted on every 429 hit.
 * Stale entries (no hit in > STALE_DAYS days) are pruned on open and reset.
 */

import fs from 'node:fs'
import path from 'node:path'

import Database from 'better-sqlite3'

import type { ILogger } from '../../types/interfaces.js'
import { getDataDir } from '../utils/paths.js'


const DB_FILENAME = 'rate-limits.db'
const SCHEMA_VERSION = 1

/** Entries not hit within this many days are considered stale and pruned. */
const DEFAULT_STALE_DAYS = 30


export interface PersistedLimit {
  providerId: string
  model: string
  windowLabel: string
  observedCount: number
  safeCount: number
  lastHitAt: number   // Unix ms
  hitCount: number
  updatedAt: number   // Unix ms
}


/**
 * Lightweight synchronous SQLite store for adaptive rate-limit data.
 * All methods are synchronous to match the sync call sites in CentralizedProvider.
 */
export class RateLimitStore {
  private db: Database.Database
  private logger: ILogger

  /** Prepared statements — compiled once, reused on every call. */
  private stmts: {
    upsert: Database.Statement
    loadAll: Database.Statement
    loadByProvider: Database.Statement
    deleteByProvider: Database.Statement
    pruneStale: Database.Statement
    count: Database.Statement
  }

  constructor(dbPath: string, logger: ILogger) {
    this.logger = logger

    this.db = new Database(dbPath)
    this.db.pragma('journal_mode = WAL')
    this.db.pragma('synchronous = NORMAL')
    this.db.pragma('busy_timeout = 3000')

    this.migrate()

    this.stmts = {
      upsert: this.db.prepare(`
        INSERT INTO provider_rate_limits
          (provider_id, model, window_label, observed_count, safe_count, last_hit_at, hit_count, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (provider_id, model, window_label) DO UPDATE SET
          observed_count = excluded.observed_count,
          safe_count     = excluded.safe_count,
          last_hit_at    = excluded.last_hit_at,
          hit_count      = excluded.hit_count,
          updated_at     = excluded.updated_at
      `),

      loadAll: this.db.prepare(`
        SELECT provider_id, model, window_label, observed_count, safe_count, last_hit_at, hit_count, updated_at
        FROM provider_rate_limits
        ORDER BY provider_id, model, window_label
      `),

      loadByProvider: this.db.prepare(`
        SELECT provider_id, model, window_label, observed_count, safe_count, last_hit_at, hit_count, updated_at
        FROM provider_rate_limits
        WHERE provider_id = ?
        ORDER BY model, window_label
      `),

      deleteByProvider: this.db.prepare(`
        DELETE FROM provider_rate_limits WHERE provider_id = ?
      `),

      pruneStale: this.db.prepare(`
        DELETE FROM provider_rate_limits
        WHERE last_hit_at < ?
      `),

      count: this.db.prepare(`
        SELECT COUNT(*) as c FROM provider_rate_limits
      `),
    }
  }


  /** Open (or create) the store at the standard data-dir location. */
  static open(logger: ILogger, dataDir?: string, staleDays = DEFAULT_STALE_DAYS): RateLimitStore {
    const dir = dataDir ?? getDataDir()
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })

    const dbPath = path.join(dir, DB_FILENAME)
    const store = new RateLimitStore(dbPath, logger)

    const pruned = store.pruneStale(staleDays)
    const { c } = store.stmts.count.get() as { c: number }
    logger.info('RateLimitStore opened', { dbPath, entriesAfterPrune: c, pruned })

    return store
  }


  /** Upsert a single learned limit entry. Called on every 429 hit. */
  save(entry: PersistedLimit): void {
    try {
      this.stmts.upsert.run(
        entry.providerId,
        entry.model,
        entry.windowLabel,
        entry.observedCount,
        entry.safeCount,
        entry.lastHitAt,
        entry.hitCount,
        entry.updatedAt,
      )
    } catch (err) {
      // Non-fatal — in-memory state is source-of-truth; persistence is best-effort
      this.logger.warn('RateLimitStore: failed to save entry', {
        providerId: entry.providerId,
        model: entry.model,
        windowLabel: entry.windowLabel,
        error: String(err),
      })
    }
  }


  /** Load all persisted limits for a given provider. */
  loadForProvider(providerId: string): PersistedLimit[] {
    try {
      return (this.stmts.loadByProvider.all(providerId) as any[]).map(rowToEntry)
    } catch (err) {
      this.logger.warn('RateLimitStore: failed to load limits', { providerId, error: String(err) })
      return []
    }
  }


  /** Load all persisted limits across all providers (e.g. for admin/metrics). */
  loadAll(): PersistedLimit[] {
    try {
      return (this.stmts.loadAll.all() as any[]).map(rowToEntry)
    } catch (err) {
      this.logger.warn('RateLimitStore: failed to load all limits', { error: String(err) })
      return []
    }
  }


  /** Delete all persisted limits for a provider (called from resetRateLimitHistory). */
  clearProvider(providerId: string): void {
    try {
      const info = this.stmts.deleteByProvider.run(providerId)
      this.logger.info('RateLimitStore: cleared limits for provider', {
        providerId,
        deleted: info.changes,
      })
    } catch (err) {
      this.logger.warn('RateLimitStore: failed to clear provider', { providerId, error: String(err) })
    }
  }


  /** Remove entries whose last_hit_at is older than staleDays. Returns deleted count. */
  pruneStale(staleDays = DEFAULT_STALE_DAYS): number {
    try {
      const cutoff = Date.now() - staleDays * 24 * 60 * 60 * 1000
      const info = this.stmts.pruneStale.run(cutoff)
      return info.changes
    } catch (err) {
      this.logger.warn('RateLimitStore: prune failed', { error: String(err) })
      return 0
    }
  }


  close(): void {
    try {
      this.db.close()
    } catch {
      // Best-effort
    }
  }


  // ── Schema ────────────────────────────────────────────────────────────────

  private migrate(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER NOT NULL
      );

      CREATE TABLE IF NOT EXISTS provider_rate_limits (
        provider_id   TEXT    NOT NULL,
        model         TEXT    NOT NULL,
        window_label  TEXT    NOT NULL,
        observed_count INTEGER NOT NULL,
        safe_count    INTEGER NOT NULL,
        last_hit_at   INTEGER NOT NULL,
        hit_count     INTEGER NOT NULL,
        updated_at    INTEGER NOT NULL,
        PRIMARY KEY (provider_id, model, window_label)
      );

      CREATE INDEX IF NOT EXISTS idx_rll_provider ON provider_rate_limits (provider_id);
      CREATE INDEX IF NOT EXISTS idx_rll_last_hit ON provider_rate_limits (last_hit_at);
    `)

    const row = this.db.prepare('SELECT version FROM schema_version').get() as { version: number } | undefined
    if (!row) {
      this.db.prepare('INSERT INTO schema_version (version) VALUES (?)').run(SCHEMA_VERSION)
      this.logger.debug('RateLimitStore: schema v1 created')
    }
  }
}


// ── Helpers ─────────────────────────────────────────────────────────────────

function rowToEntry(row: any): PersistedLimit {
  return {
    providerId:    row.provider_id,
    model:         row.model,
    windowLabel:   row.window_label,
    observedCount: row.observed_count,
    safeCount:     row.safe_count,
    lastHitAt:     row.last_hit_at,
    hitCount:      row.hit_count,
    updatedAt:     row.updated_at,
  }
}
