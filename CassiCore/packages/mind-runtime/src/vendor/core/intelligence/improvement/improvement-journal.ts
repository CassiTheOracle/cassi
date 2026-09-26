/**
 * Improvement Journal — SQLite-backed persistent log of all improvement attempts.
 *
 * Records every proposal → gate → verdict cycle with full traceability,
 * and provides aggregate statistics for the meta-learning pass.
 */

import type Database from 'better-sqlite3'
import type { ILogger } from '@cassicore/foundation'
import type {
  ImprovementEntry,
  ImprovementVerdict,
  ImprovementTrigger,
  ImprovementVerificationStatus,
  ImprovementProposalClass,
  JournalStats,
  AdaptationType,
} from './types.js'

export class ImprovementJournal {
  private readonly logger: ILogger
  private db?: Database.Database

  constructor(logger: ILogger) {
    this.logger = logger.child?.('improvement-journal') ?? logger
  }


  initialize(db: Database.Database): void {
    this.db = db
    this.initSchema()
    this.logger.info('Initialized')
  }

  private initSchema(): void {
    if (!this.db) return

    this.db.exec(`
      CREATE TABLE IF NOT EXISTS improvement_journal (
        id TEXT PRIMARY KEY,
        proposal_id TEXT NOT NULL,
        trigger TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'unknown',
        proposal_class TEXT NOT NULL DEFAULT 'heuristic',
        hypothesis TEXT NOT NULL,
        adaptation_type TEXT NOT NULL,
        config_json TEXT NOT NULL,
        dedupe_key TEXT,
        confidence REAL NOT NULL DEFAULT 0,
        quality_score REAL NOT NULL DEFAULT 0,
        evidence_json TEXT,
        gate_mode TEXT NOT NULL,
        gate_verdict TEXT NOT NULL,
        verification_status TEXT NOT NULL DEFAULT 'unverified',
        regressions_json TEXT NOT NULL DEFAULT '[]',
        improvements_json TEXT NOT NULL DEFAULT '[]',
        verdict TEXT NOT NULL,
        revert_reason TEXT,
        learnings_json TEXT NOT NULL DEFAULT '[]',
        created_at INTEGER NOT NULL,
        concluded_at INTEGER
      );

      CREATE INDEX IF NOT EXISTS idx_ij_trigger ON improvement_journal(trigger);
      CREATE INDEX IF NOT EXISTS idx_ij_verdict ON improvement_journal(verdict);
      CREATE INDEX IF NOT EXISTS idx_ij_created ON improvement_journal(created_at);
      CREATE INDEX IF NOT EXISTS idx_ij_adaptation ON improvement_journal(adaptation_type);
    `)

    const columns = this.db.prepare(`PRAGMA table_info(improvement_journal)`).all() as Array<{ name: string }>
    const names = new Set(columns.map(col => col.name))
    const migrations: string[] = []

    if (!names.has('source')) migrations.push(`ALTER TABLE improvement_journal ADD COLUMN source TEXT NOT NULL DEFAULT 'unknown'`)
    if (!names.has('proposal_class')) migrations.push(`ALTER TABLE improvement_journal ADD COLUMN proposal_class TEXT NOT NULL DEFAULT 'heuristic'`)
    if (!names.has('dedupe_key')) migrations.push(`ALTER TABLE improvement_journal ADD COLUMN dedupe_key TEXT`)
    if (!names.has('confidence')) migrations.push(`ALTER TABLE improvement_journal ADD COLUMN confidence REAL NOT NULL DEFAULT 0`)
    if (!names.has('quality_score')) migrations.push(`ALTER TABLE improvement_journal ADD COLUMN quality_score REAL NOT NULL DEFAULT 0`)
    if (!names.has('evidence_json')) migrations.push(`ALTER TABLE improvement_journal ADD COLUMN evidence_json TEXT`)
    if (!names.has('verification_status')) migrations.push(`ALTER TABLE improvement_journal ADD COLUMN verification_status TEXT NOT NULL DEFAULT 'unverified'`)

    for (const sql of migrations) {
      this.db.exec(sql)
    }

    this.db.exec(`
      CREATE INDEX IF NOT EXISTS idx_ij_dedupe ON improvement_journal(dedupe_key);
    `)
  }


  /** Record a new improvement entry */
  record(entry: ImprovementEntry): void {
    if (!this.db) return

    try {
      this.db.prepare(`
        INSERT OR REPLACE INTO improvement_journal
          (id, proposal_id, trigger, source, proposal_class, hypothesis,
           adaptation_type, config_json, dedupe_key, confidence, quality_score,
           evidence_json, gate_mode, gate_verdict, verification_status,
           regressions_json, improvements_json, verdict, revert_reason,
           learnings_json, created_at, concluded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `).run(
        entry.id,
        entry.proposalId,
        entry.trigger,
        entry.source,
        entry.proposalClass,
        entry.hypothesis,
        entry.adaptation,
        JSON.stringify(entry.config),
        entry.dedupeKey ?? null,
        entry.confidence,
        entry.qualityScore,
        entry.evidence ? JSON.stringify(entry.evidence) : null,
        entry.gateMode,
        entry.gateVerdict,
        entry.verificationStatus,
        JSON.stringify(entry.regressions),
        JSON.stringify(entry.improvements),
        entry.verdict,
        entry.revertReason ?? null,
        JSON.stringify(entry.learnings),
        entry.createdAt,
        entry.concludedAt ?? null,
      )
    } catch (err) {
      this.logger.error('Failed to record entry', { error: String(err) })
    }
  }

  /** Update an entry with final verdict and learnings */
  conclude(id: string, verdict: ImprovementVerdict, learnings: string[]): void {
    if (!this.db) return

    try {
      this.db.prepare(`
        UPDATE improvement_journal
        SET verdict = ?, learnings_json = ?, concluded_at = ?
        WHERE id = ?
      `).run(verdict, JSON.stringify(learnings), Date.now(), id)
    } catch (err) {
      this.logger.error('Failed to conclude entry', { error: String(err), id })
    }
  }


  /** Query journal entries with optional filters */
  query(opts: {
    trigger?: ImprovementTrigger
    verdict?: ImprovementVerdict
    adaptation?: AdaptationType
    since?: number
    limit?: number
  } = {}): ImprovementEntry[] {
    if (!this.db) return []

    const conditions: string[] = []
    const params: unknown[] = []

    if (opts.trigger) {
      conditions.push('trigger = ?')
      params.push(opts.trigger)
    }
    if (opts.verdict) {
      conditions.push('verdict = ?')
      params.push(opts.verdict)
    }
    if (opts.adaptation) {
      conditions.push('adaptation_type = ?')
      params.push(opts.adaptation)
    }
    if (opts.since) {
      conditions.push('created_at > ?')
      params.push(opts.since)
    }

    const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : ''
    const limit = opts.limit ?? 50

    try {
      const rows = this.db.prepare(`
        SELECT * FROM improvement_journal
        ${where}
        ORDER BY created_at DESC
        LIMIT ?
      `).all(...params, limit) as any[]

      return rows.map(this.rowToEntry)
    } catch (err) {
      this.logger.error('Query failed', { error: String(err) })
      return []
    }
  }

  /** Get aggregate statistics for meta-learning */
  getStats(): JournalStats {
    if (!this.db) {
      return { total: 0, verified: 0, unverified: 0, confirmed: 0, reverted: 0, inconclusive: 0, revertRate: 0, byTrigger: {}, byAdaptationType: {} }
    }

    try {
      const rows = this.db.prepare(`
        SELECT trigger, adaptation_type, verdict, verification_status, COUNT(*) as cnt
        FROM improvement_journal
        GROUP BY trigger, adaptation_type, verdict, verification_status
      `).all() as any[]

      let total = 0, verified = 0, unverified = 0, confirmed = 0, reverted = 0, inconclusive = 0
      const byTrigger: Record<string, { total: number; verified: number; unverified: number; confirmed: number; reverted: number; revertRate: number }> = {}
      const byAdaptationType: Record<string, { total: number; verified: number; unverified: number; confirmed: number; reverted: number; revertRate: number }> = {}

      for (const row of rows) {
        const cnt = row.cnt as number
        total += cnt
        if (row.verification_status === 'verified') verified += cnt
        else unverified += cnt

        if (row.verdict === 'confirmed') confirmed += cnt
        else if (row.verdict === 'reverted') reverted += cnt
        else inconclusive += cnt

        // By trigger
        if (!byTrigger[row.trigger]) {
          byTrigger[row.trigger] = { total: 0, verified: 0, unverified: 0, confirmed: 0, reverted: 0, revertRate: 0 }
        }
        byTrigger[row.trigger].total += cnt
        if (row.verification_status === 'verified') byTrigger[row.trigger].verified += cnt
        else byTrigger[row.trigger].unverified += cnt
        if (row.verdict === 'confirmed') byTrigger[row.trigger].confirmed += cnt
        if (row.verdict === 'reverted') byTrigger[row.trigger].reverted += cnt

        // By adaptation type
        if (!byAdaptationType[row.adaptation_type]) {
          byAdaptationType[row.adaptation_type] = { total: 0, verified: 0, unverified: 0, confirmed: 0, reverted: 0, revertRate: 0 }
        }
        byAdaptationType[row.adaptation_type].total += cnt
        if (row.verification_status === 'verified') byAdaptationType[row.adaptation_type].verified += cnt
        else byAdaptationType[row.adaptation_type].unverified += cnt
        if (row.verdict === 'confirmed') byAdaptationType[row.adaptation_type].confirmed += cnt
        if (row.verdict === 'reverted') byAdaptationType[row.adaptation_type].reverted += cnt
      }

      // Compute revert rates
      const revertRate = total > 0 ? reverted / total : 0
      for (const v of Object.values(byTrigger)) {
        v.revertRate = v.total > 0 ? v.reverted / v.total : 0
      }
      for (const v of Object.values(byAdaptationType)) {
        v.revertRate = v.total > 0 ? v.reverted / v.total : 0
      }

      return { total, verified, unverified, confirmed, reverted, inconclusive, revertRate, byTrigger, byAdaptationType }
    } catch (err) {
      this.logger.error('Stats query failed', { error: String(err) })
      return { total: 0, verified: 0, unverified: 0, confirmed: 0, reverted: 0, inconclusive: 0, revertRate: 0, byTrigger: {}, byAdaptationType: {} }
    }
  }

  hasRecentProposal(dedupeKey: string, since: number): boolean {
    if (!this.db) return false

    try {
      const row = this.db.prepare(`
        SELECT 1
        FROM improvement_journal
        WHERE dedupe_key = ? AND created_at >= ?
        LIMIT 1
      `).get(dedupeKey, since) as { 1?: number } | undefined

      return !!row
    } catch (err) {
      this.logger.error('Recent proposal query failed', { error: String(err), dedupeKey })
      return false
    }
  }

  /** Get recent learnings for context injection */
  getRecentLearnings(limit = 10): string[] {
    if (!this.db) return []

    try {
      const rows = this.db.prepare(`
        SELECT learnings_json FROM improvement_journal
        WHERE concluded_at IS NOT NULL AND learnings_json != '[]'
        ORDER BY concluded_at DESC
        LIMIT ?
      `).all(limit) as any[]

      const learnings: string[] = []
      for (const row of rows) {
        try {
          const parsed = JSON.parse(row.learnings_json) as string[]
          learnings.push(...parsed)
        } catch { /* skip malformed */ }
      }
      return learnings.slice(0, limit)
    } catch {
      return []
    }
  }


  private rowToEntry(row: any): ImprovementEntry {
    return {
      id: row.id,
      proposalId: row.proposal_id,
      trigger: row.trigger as ImprovementTrigger,
      source: row.source ?? 'unknown',
      proposalClass: (row.proposal_class ?? 'heuristic') as ImprovementProposalClass,
      hypothesis: row.hypothesis,
      adaptation: row.adaptation_type as AdaptationType,
      config: JSON.parse(row.config_json || '{}'),
      dedupeKey: row.dedupe_key ?? undefined,
      confidence: Number(row.confidence ?? 0),
      qualityScore: Number(row.quality_score ?? 0),
      evidence: row.evidence_json ? JSON.parse(row.evidence_json) : undefined,
      gateMode: row.gate_mode,
      gateVerdict: row.gate_verdict,
      verificationStatus: (row.verification_status ?? 'unverified') as ImprovementVerificationStatus,
      regressions: JSON.parse(row.regressions_json || '[]'),
      improvements: JSON.parse(row.improvements_json || '[]'),
      verdict: row.verdict as ImprovementVerdict,
      revertReason: row.revert_reason ?? undefined,
      learnings: JSON.parse(row.learnings_json || '[]'),
      createdAt: row.created_at,
      concludedAt: row.concluded_at ?? undefined,
    }
  }
}
