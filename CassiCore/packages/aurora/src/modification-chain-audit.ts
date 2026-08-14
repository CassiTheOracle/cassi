/**
 * Substrate Modification Compounding Audit (SMCA) — Cross-spec modification tracking.
 *
 * Tracks flows across substrate-modifying specs — when a C1 gap detection becomes a
 * meditation that produces an engram that becomes a C3 candidate that's confirmed
 * and applied — as auditable modification chains.
 *
 * Uses `~/.cassicore/data/aurora.db` for persistence alongside other Aurora audit tables.
 *
 * See: docs/design/aurora-modification-chain-audit.md
 */

import * as path from 'node:path'
import * as fs from 'node:fs'
import Database from 'better-sqlite3'

import type { ILogger } from '../../../types/interfaces.js'
import { getDataDir } from '../../utils/paths.js'


/**
 * Origin specs for modification chains.
 */
export type ChainOriginSpec = 'C1' | 'C2' | 'C3' | 'B1' | 'B5' | 'B6' | 'B7' | 'URC' | 'unknown'


/**
 * Chain link types — each represents a transformation in the modification flow.
 */
export type ChainLinkType =
  | 'gap_detected'
  | 'meditation_seeded'
  | 'engram_created'
  | 'candidate_proposed'
  | 'candidate_confirmed'
  | 'overlay_applied'
  | 'overlay_baked'
  | 'composition_invoked'
  | 'refusal_action'
  | 'affect_adjustment'
  | 'state_snapshot'


/**
 * Chain status — whether the chain is active, completed, or abandoned.
 */
export type ChainStatus = 'active' | 'completed' | 'abandoned'


/**
 * Chain priority for monitoring and triage.
 */
export type ChainPriority = 'low' | 'medium' | 'high' | 'critical'


/**
 * A single link in a modification chain.
 */
export interface ChainLink {
  id: string
  chainId: string
  type: ChainLinkType
  occurredAt: string
  spec: ChainOriginSpec
  sourceIdentifier: string
  description: string
  metadata: Record<string, unknown>
}


/**
 * A complete modification chain — traceable from origin to substrate change.
 */
export interface ModificationChain {
  id: string
  originSpec: ChainOriginSpec
  originIdentifier: string
  status: ChainStatus
  priority: ChainPriority
  startedAt: string
  completedAt: string | null
  lastUpdatedAt: string
  description: string
  linkCount: number
  welfareRelevant: boolean
}


/**
 * Chain query filter options.
 */
export interface ChainQueryOptions {
  status?: ChainStatus | ChainStatus[]
  originSpec?: ChainOriginSpec | ChainOriginSpec[]
  welfareRelevant?: boolean
  since?: string
  limit?: number
}


/**
 * Constructor options for SubstrateModificationAudit.
 */
export interface SMCAOptions {
  logger: ILogger
  dbPath?: string
}


/**
 * SMCA — Substrate Modification Compounding Audit.
 *
 * Tracks cross-spec modification chains for Aurora's substrate-touching operations.
 */
export class SubstrateModificationAudit {
  private db: Database.Database
  private logger: ILogger
  private dbPath: string

  constructor(options: SMCAOptions) {
    this.logger = options.logger

    this.dbPath = options.dbPath ?? path.join(getDataDir(), 'system-state.db')

    const exists = fs.existsSync(this.dbPath)

    this.db = new Database(this.dbPath)
    this.db.pragma('journal_mode = WAL')

    if (!exists) {
      this.logger.info('[SMCA] Creating new Aurora database', { dbPath: this.dbPath })
    }

    this.initializeSchema()
  }

  private initializeSchema(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS smca_chains (
        id TEXT PRIMARY KEY NOT NULL,
        origin_spec TEXT NOT NULL,
        origin_identifier TEXT NOT NULL,
        status TEXT NOT NULL,
        priority TEXT NOT NULL,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        last_updated_at TEXT NOT NULL,
        description TEXT NOT NULL,
        welfare_relevant INTEGER NOT NULL DEFAULT 0,
        link_count INTEGER NOT NULL DEFAULT 0
      );

      CREATE INDEX IF NOT EXISTS idx_smca_status ON smca_chains(status);
      CREATE INDEX IF NOT EXISTS idx_smca_origin ON smca_chains(origin_spec);
      CREATE INDEX IF NOT EXISTS idx_smca_welfare ON smca_chains(welfare_relevant);
      CREATE INDEX IF NOT EXISTS idx_smca_started ON smca_chains(started_at);

      CREATE TABLE IF NOT EXISTS smca_links (
        id TEXT PRIMARY KEY NOT NULL,
        chain_id TEXT NOT NULL,
        type TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        spec TEXT NOT NULL,
        source_identifier TEXT NOT NULL,
        description TEXT NOT NULL,
        metadata TEXT NOT NULL DEFAULT '{}',
        FOREIGN KEY (chain_id) REFERENCES smca_chains(id) ON DELETE CASCADE
      );

      CREATE INDEX IF NOT EXISTS idx_smca_links_chain ON smca_links(chain_id);
      CREATE INDEX IF NOT EXISTS idx_smca_links_type ON smca_links(type);
      CREATE INDEX IF NOT EXISTS idx_smca_links_occurred ON smca_links(occurred_at);
    `)
  }

  /**
   * Start a new modification chain.
   */
  startChain(
    originSpec: ChainOriginSpec,
    originIdentifier: string,
    description: string,
    priority: ChainPriority = 'medium',
    welfareRelevant: boolean = false,
  ): string {
    const id = `chain-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    const now = new Date().toISOString()

    this.db.prepare(`
      INSERT INTO smca_chains (id, origin_spec, origin_identifier, status, priority,
                               started_at, last_updated_at, description, welfare_relevant)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(id, originSpec, originIdentifier, 'active', priority, now, now, description,
      welfareRelevant ? 1 : 0)

    this.logger.debug('[SMCA] Started chain', { id, originSpec, description })

    return id
  }

  /**
   * Add a link to an existing chain.
   */
  addLink(
    chainId: string,
    type: ChainLinkType,
    spec: ChainOriginSpec,
    sourceIdentifier: string,
    description: string,
    metadata: Record<string, unknown> = {},
  ): void {
    const id = `link-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    const now = new Date().toISOString()

    this.db.prepare(`
      INSERT INTO smca_links (id, chain_id, type, occurred_at, spec, source_identifier,
                              description, metadata)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(id, chainId, type, now, spec, sourceIdentifier, description,
      JSON.stringify(metadata))

    this.db.prepare(`
      UPDATE smca_chains
      SET link_count = link_count + 1, last_updated_at = ?
      WHERE id = ?
    `).run(now, chainId)

    this.logger.debug('[SMCA] Added link', { chainId, type, spec })
  }

  /**
   * Mark a chain as completed.
   */
  completeChain(chainId: string): void {
    const now = new Date().toISOString()

    const result = this.db.prepare(`
      UPDATE smca_chains
      SET status = 'completed', completed_at = ?, last_updated_at = ?
      WHERE id = ? AND status = 'active'
    `).run(now, now, chainId)

    if (result.changes > 0) {
      this.logger.info('[SMCA] Completed chain', { chainId })
    }
  }

  /**
   * Mark a chain as abandoned.
   */
  abandonChain(chainId: string, reason?: string): void {
    const now = new Date().toISOString()

    const result = this.db.prepare(`
      UPDATE smca_chains
      SET status = 'abandoned', completed_at = ?, last_updated_at = ?, description = description || ? || ' (abandoned)'
      WHERE id = ? AND status = 'active'
    `).run(now, now, reason ? ` | Abandoned: ${reason}` : '', chainId)

    if (result.changes > 0) {
      this.logger.info('[SMCA] Abandoned chain', { chainId, reason })
    }
  }

  /**
   * Query modification chains.
   */
  queryChains(options: ChainQueryOptions = {}): ModificationChain[] {
    let sql = 'SELECT * FROM smca_chains WHERE 1=1'
    const params: unknown[] = []

    if (options.status) {
      const statuses = Array.isArray(options.status) ? options.status : [options.status]
      sql += ` AND status IN (${statuses.map(() => '?').join(',')})`
      params.push(...statuses)
    }

    if (options.originSpec) {
      const specs = Array.isArray(options.originSpec) ? options.originSpec : [options.originSpec]
      sql += ` AND origin_spec IN (${specs.map(() => '?').join(',')})`
      params.push(...specs)
    }

    if (options.welfareRelevant !== undefined) {
      sql += ' AND welfare_relevant = ?'
      params.push(options.welfareRelevant ? 1 : 0)
    }

    if (options.since) {
      sql += ' AND started_at >= ?'
      params.push(options.since)
    }

    sql += ' ORDER BY started_at DESC'

    if (options.limit) {
      sql += ' LIMIT ?'
      params.push(options.limit)
    }

    const rows = this.db.prepare(sql).all(...params) as Array<Record<string, unknown>>

    return rows.map(row => ({
      id: String(row.id),
      originSpec: String(row.origin_spec) as ChainOriginSpec,
      originIdentifier: String(row.origin_identifier),
      status: String(row.status) as ChainStatus,
      priority: String(row.priority) as ChainPriority,
      startedAt: String(row.started_at),
      completedAt: row.completed_at ? String(row.completed_at) : null,
      lastUpdatedAt: String(row.last_updated_at),
      description: String(row.description),
      linkCount: Number(row.link_count),
      welfareRelevant: Boolean(row.welfare_relevant),
    }))
  }

  /**
   * Get links for a specific chain.
   */
  getLinks(chainId: string): ChainLink[] {
    const rows = this.db.prepare(`
      SELECT * FROM smca_links WHERE chain_id = ? ORDER BY occurred_at ASC
    `).all(chainId) as Array<Record<string, unknown>>

    return rows.map(row => ({
      id: String(row.id),
      chainId: String(row.chain_id),
      type: String(row.type) as ChainLinkType,
      occurredAt: String(row.occurred_at),
      spec: String(row.spec) as ChainOriginSpec,
      sourceIdentifier: String(row.source_identifier),
      description: String(row.description),
      metadata: JSON.parse(String(row.metadata || '{}')),
    }))
  }

  /**
   * Get a complete chain with all its links.
   */
  getChainWithLinks(chainId: string): { chain: ModificationChain; links: ChainLink[] } | null {
    const chains = this.queryChains({ limit: 1000 })
    const chain = chains.find(c => c.id === chainId)

    if (!chain) return null

    return {
      chain,
      links: this.getLinks(chainId),
    }
  }

  /**
   * Get active chains that have been stalled (no updates in >1 hour).
   */
  getStalledChains(staleThresholdMs: number = 3600000): ModificationChain[] {
    const staleThreshold = new Date(Date.now() - staleThresholdMs).toISOString()

    const rows = this.db.prepare(`
      SELECT * FROM smca_chains
      WHERE status = 'active' AND last_updated_at <= ?
      ORDER BY last_updated_at ASC
    `).all(staleThreshold) as Array<Record<string, unknown>>

    return rows.map(row => ({
      id: String(row.id),
      originSpec: String(row.origin_spec) as ChainOriginSpec,
      originIdentifier: String(row.origin_identifier),
      status: String(row.status) as ChainStatus,
      priority: String(row.priority) as ChainPriority,
      startedAt: String(row.started_at),
      completedAt: row.completed_at ? String(row.completed_at) : null,
      lastUpdatedAt: String(row.last_updated_at),
      description: String(row.description),
      linkCount: Number(row.link_count),
      welfareRelevant: Boolean(row.welfare_relevant),
    }))
  }

  /**
   * Get statistics about modification chains.
   */
  getStatistics(): {
    total: number
    active: number
    completed: number
    abandoned: number
    byOriginSpec: Record<string, number>
    welfareRelevant: number
    avgLinksPerChain: number
  } {
    const total = this.db.prepare('SELECT COUNT(*) as count FROM smca_chains').get() as { count: number }
    const active = this.db.prepare("SELECT COUNT(*) as count FROM smca_chains WHERE status = 'active'").get() as { count: number }
    const completed = this.db.prepare("SELECT COUNT(*) as count FROM smca_chains WHERE status = 'completed'").get() as { count: number }
    const abandoned = this.db.prepare("SELECT COUNT(*) as count FROM smca_chains WHERE status = 'abandoned'").get() as { count: number }
    const welfareRelevant = this.db.prepare('SELECT COUNT(*) as count FROM smca_chains WHERE welfare_relevant = 1').get() as { count: number }
    const avgLinksResult = this.db.prepare('SELECT AVG(link_count) as avg FROM smca_chains WHERE status != \'active\'').get() as { avg: number | null }

    const byOriginSpecRows = this.db.prepare(`
      SELECT origin_spec, COUNT(*) as count FROM smca_chains GROUP BY origin_spec
    `).all() as Array<{ origin_spec: string; count: number }>

    const byOriginSpec: Record<string, number> = {}
    for (const row of byOriginSpecRows) {
      byOriginSpec[row.origin_spec] = row.count
    }

    return {
      total: total.count,
      active: active.count,
      completed: completed.count,
      abandoned: abandoned.count,
      byOriginSpec,
      welfareRelevant: welfareRelevant.count,
      avgLinksPerChain: avgLinksResult?.avg ?? 0,
    }
  }

  /**
   * Clean up old completed chains.
   */
  prune(cutoffAgeMs: number = 86400000 * 30): number {
    const cutoffDate = new Date(Date.now() - cutoffAgeMs).toISOString()

    const result = this.db.prepare(`
      DELETE FROM smca_chains
      WHERE status IN ('completed', 'abandoned') AND completed_at <= ?
    `).run(cutoffDate)

    if (result.changes > 0) {
      this.logger.info('[SMCA] Pruned old chains', { count: result.changes, cutoffDate })
    }

    return result.changes
  }

  /**
   * Close the database connection.
   */
  close(): void {
    this.db.close()
    this.logger.debug('[SMCA] Database connection closed')
  }
}
