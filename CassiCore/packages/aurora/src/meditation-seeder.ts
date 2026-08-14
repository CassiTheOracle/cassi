/**
 * MeditationSeeder — Converts gap candidates into directed meditation seeds.
 *
 * C1.2 of Aurora Self-Curing Topology. Takes GapCandidates from the GapDetector,
 * evaluates their priority, and produces MeditationSeeds that the existing
 * meditation system can consume via focused seeding.
 *
 * Seed generation is a local computation (no LLM call). The seed provides
 * structured context that the meditation system's own LLM steps use.
 * This keeps the seeder lightweight and deterministic.
 *
 * See: docs/design/aurora-self-curing-topology.md §3-4
 */

import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

import Database from 'better-sqlite3'

import type { ILogger } from '../../../types/interfaces.js'
import type { GapCandidate, GapCategory } from './gap-detector.js'



export interface MeditationSeed {
  id: string
  gapId: string
  topic: string
  entryPoints: string[]
  expectedRefinement: string
  budget: { maxTurns: number; maxCostUsd: number }
  proposedAt: string
  proposedBy: 'curator'
  metadata: Record<string, unknown>
}

export interface SeedConfig {
  maxTurnsPerSeed: number
  maxCostUsdPerSeed: number
  maxFractionOfMeditationTime: number
  cooldownHours: number
  maxPendingSeeds: number
}

export interface SeedingResult {
  seeds: MeditationSeed[]
  skipped: Array<{ gapId: string; reason: string }>
}

type SeedStatus = 'pending' | 'scheduled' | 'running' | 'resolved' | 'expired' | 'abandoned' | 'left_open'

interface SeedRow {
  id: string
  gap_id: string
  topic: string
  entry_points: string
  expected_refinement: string
  max_turns: number
  max_cost_usd: number
  proposed_at: string
  proposed_by: string
  status: string
  scheduled_at: string | null
  executed_at: string | null
  resolved_at: string | null
  result_summary: string | null
  metadata: string
}


const DEFAULT_CONFIG: SeedConfig = {
  maxTurnsPerSeed: 15,
  maxCostUsdPerSeed: 0.25,
  maxFractionOfMeditationTime: 0.20,
  cooldownHours: 24,
  maxPendingSeeds: 5,
}

const CATEGORY_PROMPTS: Record<GapCategory, { topicTemplate: string; refinementTemplate: string }> = {
  underconnected: {
    topicTemplate: 'Explore connections between these related but poorly linked concepts',
    refinementTemplate: 'At least 2 new edges connecting previously isolated subgraph members',
  },
  fragmented: {
    topicTemplate: 'Bridge the conceptual gap between these disjoint clusters',
    refinementTemplate: 'At least 1 connecting concept or edge between previously separate components',
  },
  missing_focus: {
    topicTemplate: 'Develop deeper understanding of this high-attention, low-integration concept',
    refinementTemplate: 'Increased coherence score for the targeted concept',
  },
  isolated_nucleus: {
    topicTemplate: 'Investigate why this concept cluster has no external connections',
    refinementTemplate: 'At least 1 edge connecting the isolated cluster to the broader graph',
  },
}



const SCHEMA_V1 = `
  CREATE TABLE IF NOT EXISTS meditation_seeds_schema_version (
    version INTEGER PRIMARY KEY
  );

  CREATE TABLE IF NOT EXISTS meditation_seeds (
    id                  TEXT PRIMARY KEY,
    gap_id              TEXT NOT NULL,
    topic               TEXT NOT NULL,
    entry_points        TEXT NOT NULL DEFAULT '[]',
    expected_refinement TEXT NOT NULL,
    max_turns           INTEGER NOT NULL DEFAULT 15,
    max_cost_usd        REAL NOT NULL DEFAULT 0.25,
    proposed_at         TEXT NOT NULL,
    proposed_by         TEXT NOT NULL DEFAULT 'curator',
    status              TEXT NOT NULL DEFAULT 'pending',
    scheduled_at        TEXT,
    executed_at         TEXT,
    resolved_at         TEXT,
    result_summary      TEXT,
    metadata            TEXT DEFAULT '{}'
  );

  CREATE INDEX IF NOT EXISTS idx_seeds_gap_id ON meditation_seeds(gap_id);
  CREATE INDEX IF NOT EXISTS idx_seeds_status ON meditation_seeds(status);
  CREATE INDEX IF NOT EXISTS idx_seeds_proposed_at ON meditation_seeds(proposed_at);

  INSERT INTO meditation_seeds_schema_version (version) VALUES (1);
`



export class MeditationSeeder {
  private readonly logger: ILogger
  private readonly db: Database.Database
  private readonly config: SeedConfig
  private readonly ownsDb: boolean

  // Prepared statements
  private stmtInsertSeed!: Database.Statement
  private stmtUpdateStatus!: Database.Statement
  private stmtGetPending!: Database.Statement
  private stmtGetByGapId!: Database.Statement
  private stmtCountPending!: Database.Statement

  constructor(
    dbOrPath: string | Database.Database,
    logger: ILogger,
    config?: Partial<SeedConfig>,
  ) {
    this.logger = logger.child ? logger.child('meditation-seeder') : logger
    this.config = { ...DEFAULT_CONFIG, ...config }

    if (typeof dbOrPath === 'string') {
      const dir = path.dirname(dbOrPath)
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
      this.db = new Database(dbOrPath)
      this.db.pragma('journal_mode = WAL')
      this.db.pragma('busy_timeout = 5000')
      this.db.pragma('synchronous = NORMAL')
      this.ownsDb = true
    } else {
      this.db = dbOrPath
      this.ownsDb = false
    }

    this.initSchema()
    this.prepareStatements()
    this.logger.info('MeditationSeeder initialized')
  }



  /**
   * Convert gap candidates into meditation seeds.
   * Skips gaps that are already covered by pending seeds or are in cooldown.
   */
  seedFromGaps(gaps: GapCandidate[]): SeedingResult {
    const results: MeditationSeed[] = []
    const skipped: Array<{ gapId: string; reason: string }> = []

    const pendingCount = this.countPendingSeeds()
    let budgetRemaining = Math.max(0, this.config.maxPendingSeeds - pendingCount)

    // Sort gaps by priority (highest first)
    const sorted = [...gaps].sort((a, b) => b.priority - a.priority)

    for (const gap of sorted) {
      if (budgetRemaining <= 0) {
        skipped.push({ gapId: gap.id, reason: 'seed budget exhausted' })
        continue
      }

      // Skip if gap already has a pending or scheduled seed
      const existing = this.stmtGetByGapId.all(gap.id) as SeedRow[]
      const activeExisting = existing.filter(
        r => r.status === 'pending' || r.status === 'scheduled' || r.status === 'running',
      )
      if (activeExisting.length > 0) {
        skipped.push({ gapId: gap.id, reason: 'already has active seed' })
        continue
      }

      // Skip if last seed for this gap was too recent (cooldown)
      const recentSeed = existing
        .filter(r => r.proposed_at)
        .sort((a, b) => b.proposed_at.localeCompare(a.proposed_at))[0]
      if (recentSeed) {
        const proposedAt = new Date(recentSeed.proposed_at).getTime()
        const cooldownMs = this.config.cooldownHours * 60 * 60 * 1000
        if (Date.now() - proposedAt < cooldownMs) {
          skipped.push({ gapId: gap.id, reason: 'cooldown period active' })
          continue
        }
      }

      const seed = this.createSeed(gap)
      this.stmtInsertSeed.run(
        seed.id,
        seed.gapId,
        seed.topic,
        JSON.stringify(seed.entryPoints),
        seed.expectedRefinement,
        seed.budget.maxTurns,
        seed.budget.maxCostUsd,
        seed.proposedAt,
        seed.proposedBy,
        'pending',
        JSON.stringify(seed.metadata),
      )

      results.push(seed)
      budgetRemaining--
    }

    this.logger.info('Seeded from gaps', {
      seedsCreated: results.length,
      skipped: skipped.length,
      pendingBudget: budgetRemaining,
    })

    return { seeds: results, skipped }
  }


  /** Get all pending seeds ready for scheduling. */
  getPendingSeeds(): MeditationSeed[] {
    const rows = this.stmtGetPending.all() as SeedRow[]
    return rows.map(this.rowToSeed.bind(this))
  }


  /** Mark a seed as scheduled for execution. */
  markScheduled(seedId: string): void {
    const now = new Date().toISOString()
    this.stmtUpdateStatus.run('scheduled', now, null, null, seedId)
  }


  /** Mark a seed as running (meditation started). */
  markRunning(seedId: string): void {
    const now = new Date().toISOString()
    this.stmtUpdateStatus.run('running', null, now, null, seedId)
  }


  /** Mark a seed as resolved with a result summary. */
  markResolved(seedId: string, summary: string): void {
    const now = new Date().toISOString()
    this.stmtUpdateStatus.run('resolved', null, null, now, seedId)
  }


  /** Mark a seed as expired (budget exceeded, gap changed). */
  markExpired(seedId: string): void {
    this.stmtUpdateStatus.run('expired', null, null, null, seedId)
  }


  /** Mark a seed as abandoned (operator decision or productive uncertainty). */
  markAbandoned(seedId: string): void {
    this.stmtUpdateStatus.run('abandoned', null, null, null, seedId)
  }


  /**
   * C1.4 — mark a seed as `left_open`: a productive uncertainty the
   * curator has decided NOT to resolve, retained for projection
   * rendering as a "currently held question". Distinct from
   * `abandoned` (which suggests giving up); left_open is intentional
   * retention. The `rationale` is stored in result_summary for audit.
   */
  markLeftOpen(seedId: string, rationale: string): void {
    this.stmtUpdateStatus.run('left_open', null, null, new Date().toISOString(), seedId)
    this.db.prepare(`UPDATE meditation_seeds SET result_summary = ? WHERE id = ?`).run(rationale, seedId)
  }


  /**
   * C1.4 — list seeds currently in `left_open` state, for projection
   * rendering of "currently held questions". Returns seeds with
   * their stored rationale (in `metadata.rationale`).
   */
  getOpenQuestions(): Array<MeditationSeed & { rationale: string | null }> {
    const rows = this.db.prepare(`
      SELECT * FROM meditation_seeds WHERE status = 'left_open' ORDER BY resolved_at DESC
    `).all() as SeedRow[]
    return rows.map(row => ({
      ...this.rowToSeed(row),
      rationale: row.result_summary,
    }))
  }


  /** Get count of pending seeds. */
  countPendingSeeds(): number {
    const row = this.stmtCountPending.get() as { count: number } | undefined
    return row?.count ?? 0
  }


  /** Close the database connection. */
  close(): void {
    if (!this.ownsDb) return
    this.db.close()
  }



  private createSeed(gap: GapCandidate): MeditationSeed {
    const templates = CATEGORY_PROMPTS[gap.category]

    const signalContext = gap.signals
      .map(s => `${s.type} (${s.strength.toFixed(2)}): ${s.provenance}`)
      .join('; ')

    const topic = `${templates.topicTemplate} [${gap.scope.nodeIds.join(', ')}] — ${signalContext}`

    return {
      id: `seed_${crypto.randomUUID()}`,
      gapId: gap.id,
      topic,
      entryPoints: gap.scope.nodeIds,
      expectedRefinement: templates.refinementTemplate,
      budget: {
        maxTurns: this.config.maxTurnsPerSeed,
        maxCostUsd: this.config.maxCostUsdPerSeed,
      },
      proposedAt: new Date().toISOString(),
      proposedBy: 'curator',
      metadata: {
        gapCategory: gap.category,
        gapPriority: gap.priority,
        detectionCount: gap.detectionCount,
      },
    }
  }


  private rowToSeed(row: SeedRow): MeditationSeed {
    return {
      id: row.id,
      gapId: row.gap_id,
      topic: row.topic,
      entryPoints: JSON.parse(row.entry_points),
      expectedRefinement: row.expected_refinement,
      budget: {
        maxTurns: row.max_turns,
        maxCostUsd: row.max_cost_usd,
      },
      proposedAt: row.proposed_at,
      proposedBy: row.proposed_by as 'curator',
      metadata: JSON.parse(row.metadata),
    }
  }


  private initSchema(): void {
    let row: { version: number } | undefined
    try {
      row = this.db.prepare(
        'SELECT version FROM meditation_seeds_schema_version',
      ).get() as { version: number } | undefined
    } catch {
      // Table doesn't exist yet — fresh database
    }

    if (!row) {
      const now = new Date().toISOString()
      this.db.exec(SCHEMA_V1)
      this.logger.info('MeditationSeeder schema initialized', { version: 1, at: now })
    }
  }


  private prepareStatements(): void {
    this.stmtInsertSeed = this.db.prepare(`
      INSERT INTO meditation_seeds (id, gap_id, topic, entry_points, expected_refinement,
        max_turns, max_cost_usd, proposed_at, proposed_by, status, metadata)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `)

    this.stmtUpdateStatus = this.db.prepare(`
      UPDATE meditation_seeds
      SET status = ?,
          scheduled_at = COALESCE(?, scheduled_at),
          executed_at = COALESCE(?, executed_at),
          resolved_at = COALESCE(?, resolved_at)
      WHERE id = ?
    `)

    this.stmtGetPending = this.db.prepare(
      "SELECT * FROM meditation_seeds WHERE status = 'pending' ORDER BY proposed_at ASC",
    )

    this.stmtGetByGapId = this.db.prepare(
      'SELECT * FROM meditation_seeds WHERE gap_id = ? ORDER BY proposed_at DESC',
    )

    this.stmtCountPending = this.db.prepare(
      "SELECT COUNT(*) as count FROM meditation_seeds WHERE status = 'pending'",
    )
  }
}
