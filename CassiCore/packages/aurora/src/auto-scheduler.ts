/**
 * AutoScheduler — Decides whether to auto-schedule directed meditations or
 * flag gaps for human review.
 *
 * C1.3 of Aurora Self-Curing Topology. Consumes MeditationSeeds from the
 * MeditationSeeder and applies budget enforcement, risk assessment, and
 * welfare guards to determine whether each seed should be:
 *   - Auto-scheduled (within budget, low risk)
 *   - Flagged for human review (high risk, welfare concern)
 *   - Deferred (budget exhausted, cooldown active)
 *
 * Welfare guards enforced:
 *   C1.W5 — Anxious-loop guard: if directed meditations exceed a configured
 *            fraction of total meditations, scheduling pauses and the flag fires.
 *   C1.W6 — Hard budget cap: directed meditations cannot exceed
 *            maxFractionOfMeditationTime of total meditation budget.
 *
 * See: docs/design/aurora-self-curing-topology.md §4
 */

import * as crypto from 'node:crypto'
import * as fs from 'node:fs'
import * as path from 'node:path'

import Database from 'better-sqlite3'

import type { ILogger } from '../../../types/interfaces.js'
import type { GapCategory, GapStatus } from './gap-detector.js'
import type { MeditationSeed } from './meditation-seeder.js'
import { getDataDir } from '../../utils/paths.js'



export type SchedulingDecision = 'auto_schedule' | 'flag_for_review' | 'defer'

export type SchedulerFlag =
  | 'anxious_loop'
  | 'budget_exhausted'
  | 'daily_cap_reached'
  | 'category_cap_reached'
  | 'cooldown_active'
  | 'max_retries_reached'
  | 'high_risk'
  | 'welfare_concern'

export interface AutoSchedulerConfig {
  /** Max directed meditations auto-scheduled per day. Default: 6 */
  maxDailyAutoScheduled: number
  /** Max fraction of total meditation time for directed work. Default: 0.4 */
  maxFractionOfMeditationTime: number
  /** Total daily cost cap in USD for directed meditations. Default: 1.0 */
  totalDailyCostCapUsd: number
  /** Max concurrent directed meditations. Default: 1 */
  maxConcurrentDirected: number
  /** Max retries per gap before marking unresolvable. Default: 3 */
  maxRetriesPerGap: number
  /** Hours between retries on the same gap. Default: 24 */
  cooldownHours: number
  /** Per-category daily caps. Default: 2 each */
  categoryCaps: Record<GapCategory, number>
  /** Priority threshold above which gaps are flagged for review. Default: 0.8 */
  highRiskPriorityThreshold: number
  /**
   * Fraction of completed meditations that must be directed before the
   * anxious-loop guard fires. Default: 0.6 (if >60% of recent meditations
   * are directed, the system is self-curing too aggressively).
   */
  anxiousLoopFraction: number
  /**
   * Number of recent meditations to consider for the anxious-loop check.
   * Default: 10
   */
  anxiousLoopWindow: number
  /** Whether auto-scheduling is enabled. Default: false (requires opt-in) */
  enabled: boolean
}

export interface SchedulingResult {
  seedId: string
  gapId: string
  decision: SchedulingDecision
  flags: SchedulerFlag[]
  reason: string
  scheduledAt: string | null
}

export interface DailyBudgetState {
  date: string
  autoScheduled: number
  costUsd: number
  perCategory: Record<string, number>
}

export interface SchedulerStatus {
  enabled: boolean
  dailyBudget: DailyBudgetState
  flagsRaised: SchedulerFlag[]
  totalAutoScheduled: number
  totalDeferred: number
  totalFlaggedForReview: number
}



const SCHEMA_VERSION = 1

const SCHEMA_V1 = `
  CREATE TABLE IF NOT EXISTS scheduler_schema_version (
    version INTEGER PRIMARY KEY
  );
  INSERT OR IGNORE INTO scheduler_schema_version (version) VALUES (${SCHEMA_VERSION});

  CREATE TABLE IF NOT EXISTS scheduling_decisions (
    id              TEXT PRIMARY KEY,
    seed_id         TEXT NOT NULL,
    gap_id          TEXT NOT NULL,
    decision        TEXT NOT NULL,
    flags           TEXT NOT NULL DEFAULT '[]',
    reason          TEXT NOT NULL,
    scheduled_at    TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
  );

  CREATE TABLE IF NOT EXISTS daily_budget (
    date            TEXT PRIMARY KEY,
    auto_scheduled  INTEGER NOT NULL DEFAULT 0,
    cost_usd        REAL NOT NULL DEFAULT 0.0,
    per_category    TEXT NOT NULL DEFAULT '{}'
  );

  CREATE TABLE IF NOT EXISTS gap_retry_tracking (
    gap_id          TEXT PRIMARY KEY,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT,
    marked_unresolvable_at TEXT
  );

  CREATE INDEX IF NOT EXISTS idx_decisions_seed ON scheduling_decisions(seed_id);
  CREATE INDEX IF NOT EXISTS idx_decisions_gap ON scheduling_decisions(gap_id);
  CREATE INDEX IF NOT EXISTS idx_decisions_date ON scheduling_decisions(created_at);
`

interface DecisionRow {
  id: string
  seed_id: string
  gap_id: string
  decision: string
  flags: string
  reason: string
  scheduled_at: string | null
  created_at: string
}

interface BudgetRow {
  date: string
  auto_scheduled: number
  cost_usd: number
  per_category: string
}

interface RetryRow {
  gap_id: string
  retry_count: number
  last_attempt_at: string | null
  marked_unresolvable_at: string | null
}



const DEFAULT_CONFIG: AutoSchedulerConfig = {
  maxDailyAutoScheduled: 6,
  maxFractionOfMeditationTime: 0.4,
  totalDailyCostCapUsd: 1.0,
  maxConcurrentDirected: 1,
  maxRetriesPerGap: 3,
  cooldownHours: 24,
  categoryCaps: {
    underconnected: 2,
    fragmented: 2,
    missing_focus: 2,
    isolated_nucleus: 2,
  },
  highRiskPriorityThreshold: 0.8,
  anxiousLoopFraction: 0.6,
  anxiousLoopWindow: 10,
  enabled: false,
}



export class AutoScheduler {
  private readonly db: Database.Database
  private readonly ownsDb: boolean
  private readonly config: AutoSchedulerConfig
  private readonly logger: ILogger

  // Active flags set during the last evaluate() call
  private activeFlags: Set<SchedulerFlag> = new Set()

  // Prepared statements
  private stmtInsertDecision!: Database.Statement
  private stmtGetDecisionsByGap!: Database.Statement
  private stmtGetDailyBudget!: Database.Statement
  private stmtUpsertDailyBudget!: Database.Statement
  private stmtGetRetry!: Database.Statement
  private stmtUpsertRetry!: Database.Statement
  private stmtIncrementRetry!: Database.Statement
  private stmtMarkUnresolvable!: Database.Statement

  constructor(
    dbPathOrDb: string | Database.Database,
    config: Partial<AutoSchedulerConfig> = {},
    logger: ILogger,
  ) {
    this.config = { ...DEFAULT_CONFIG, ...config }
    // Merge category caps individually so partial overrides work
    this.config.categoryCaps = { ...DEFAULT_CONFIG.categoryCaps, ...(config.categoryCaps ?? {}) }
    this.logger = logger.child ? logger.child('aurora:auto-scheduler') : logger

    if (typeof dbPathOrDb === 'string') {
      const dir = path.dirname(dbPathOrDb)
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true })
      }
      this.db = new Database(dbPathOrDb)
      this.ownsDb = true
    } else {
      this.db = dbPathOrDb
      this.ownsDb = false
    }

    this.initSchema()
    this.prepareStatements()
  }



  /**
   * Evaluate a set of pending meditation seeds and produce scheduling decisions.
   *
   * Seeds are evaluated in priority order (highest first). Each seed gets
   * one of three decisions:
   *   - auto_schedule: within budget, low risk, no welfare concerns
   *   - flag_for_review: high risk or welfare concern
   *   - defer: budget exhausted, cooldown active, or max retries reached
   *
   * Auto-scheduled seeds are marked on the MeditationSeeder via the
   * `markScheduled` callback.
   */
  evaluate(
    seeds: MeditationSeed[],
    gapMeta: Map<string, { category: GapCategory; priority: number; status: GapStatus }>,
    totalMeditationCount: number,
    directedMeditationCount: number,
  ): SchedulingResult[] {
    if (!this.config.enabled) {
      return seeds.map(s => ({
        seedId: s.id,
        gapId: s.gapId,
        decision: 'defer' as SchedulingDecision,
        flags: [] as SchedulerFlag[],
        reason: 'Auto-scheduling is disabled',
        scheduledAt: null,
      }))
    }

    this.activeFlags.clear()

    const today = this.todayStr()
    const budget = this.getOrCreateDailyBudget(today)
    const results: SchedulingResult[] = []

    // Check anxious-loop guard first (C1.W5)
    const anxiousLoop = this.checkAnxiousLoop(totalMeditationCount, directedMeditationCount)

    // Sort seeds by gap priority (highest first)
    const sorted = [...seeds].sort((a, b) => {
      const aPri = gapMeta.get(a.gapId)?.priority ?? 0
      const bPri = gapMeta.get(b.gapId)?.priority ?? 0
      return bPri - aPri
    })

    for (const seed of sorted) {
      const meta = gapMeta.get(seed.gapId)
      if (!meta) {
        results.push(this.makeResult(seed.id, seed.gapId, 'defer', [], 'No gap metadata available'))
        continue
      }

      const decision = this.evaluateSeed(
        seed, meta, budget, today, anxiousLoop,
      )
      results.push(decision)

      // Update running budget for auto-scheduled seeds
      if (decision.decision === 'auto_schedule') {
        budget.autoScheduled += 1
        budget.costUsd += seed.budget.maxCostUsd
        budget.perCategory[meta.category] = (budget.perCategory[meta.category] ?? 0) + 1
        this.persistDailyBudget(today, budget)
        this.recordRetry(seed.gapId)
      }
    }

    return results
  }

  /** Get the current scheduler status. */
  getStatus(totalMeditationCount: number, directedMeditationCount: number): SchedulerStatus {
    const today = this.todayStr()
    const budget = this.getOrCreateDailyBudget(today)

    return {
      enabled: this.config.enabled,
      dailyBudget: budget,
      flagsRaised: Array.from(this.activeFlags),
      totalAutoScheduled: budget.autoScheduled,
      totalDeferred: this.countTodayDecisions('defer'),
      totalFlaggedForReview: this.countTodayDecisions('flag_for_review'),
    }
  }

  /** Check if the anxious-loop guard is currently triggered. */
  isAnxiousLoop(totalMeditationCount: number, directedMeditationCount: number): boolean {
    return this.checkAnxiousLoop(totalMeditationCount, directedMeditationCount)
  }

  /** Reset the daily budget (useful for testing or manual admin). */
  resetDailyBudget(): void {
    const today = this.todayStr()
    this.stmtUpsertDailyBudget.run(today, 0, 0.0, '{}')
    this.logger.info('Daily budget reset', { date: today })
  }

  /** Get the retry tracking for a specific gap. */
  getGapRetryState(gapId: string): { retryCount: number; lastAttemptAt: string | null; unresolvable: boolean } {
    const row = this.stmtGetRetry.get(gapId) as RetryRow | undefined
    return {
      retryCount: row?.retry_count ?? 0,
      lastAttemptAt: row?.last_attempt_at ?? null,
      unresolvable: row?.marked_unresolvable_at !== null && row?.marked_unresolvable_at !== undefined,
    }
  }

  /** Close the database. */
  close(): void {
    if (this.ownsDb) {
      this.db.close()
    }
  }



  private evaluateSeed(
    seed: MeditationSeed,
    meta: { category: GapCategory; priority: number; status: GapStatus },
    budget: DailyBudgetState,
    today: string,
    anxiousLoop: boolean,
  ): SchedulingResult {
    const flags: SchedulerFlag[] = []

    // Check if gap is already resolved or unresolvable
    if (meta.status === 'resolved' || meta.status === 'leave_open' || meta.status === 'unresolvable') {
      return this.makeResult(seed.id, seed.gapId, 'defer', [], `Gap status is ${meta.status}`)
    }

    // Check anxious-loop guard (C1.W5)
    if (anxiousLoop) {
      flags.push('anxious_loop')
      this.activeFlags.add('anxious_loop')
      this.persistDecision(seed.id, seed.gapId, 'defer', flags, 'Anxious-loop guard active: too many directed meditations')
      return this.makeResult(seed.id, seed.gapId, 'defer', flags, 'Anxious-loop guard active: directed fraction exceeds threshold')
    }

    // Check hard budget cap (C1.W6) — maxFractionOfMeditationTime
    // This is a structural cap; if total meditation time is unknown, we
    // check daily count and cost caps instead.
    if (budget.autoScheduled >= this.config.maxDailyAutoScheduled) {
      flags.push('daily_cap_reached')
      this.activeFlags.add('daily_cap_reached')
      this.persistDecision(seed.id, seed.gapId, 'defer', flags, `Daily auto-schedule cap reached (${this.config.maxDailyAutoScheduled})`)
      return this.makeResult(seed.id, seed.gapId, 'defer', flags, `Daily auto-schedule cap reached (${this.config.maxDailyAutoScheduled})`)
    }

    if (budget.costUsd + seed.budget.maxCostUsd > this.config.totalDailyCostCapUsd) {
      flags.push('budget_exhausted')
      this.activeFlags.add('budget_exhausted')
      this.persistDecision(seed.id, seed.gapId, 'defer', flags, `Daily cost cap would be exceeded ($${this.config.totalDailyCostCapUsd})`)
      return this.makeResult(seed.id, seed.gapId, 'defer', flags, `Daily cost cap would be exceeded ($${this.config.totalDailyCostCapUsd})`)
    }

    // Check per-category cap
    const categoryCount = budget.perCategory[meta.category] ?? 0
    const categoryCap = this.config.categoryCaps[meta.category] ?? 2
    if (categoryCount >= categoryCap) {
      flags.push('category_cap_reached')
      this.activeFlags.add('category_cap_reached')
      this.persistDecision(seed.id, seed.gapId, 'defer', flags, `Category cap reached for ${meta.category} (${categoryCap})`)
      return this.makeResult(seed.id, seed.gapId, 'defer', flags, `Category cap reached for ${meta.category} (${categoryCap})`)
    }

    // Check per-gap retry limit
    const retryState = this.getGapRetryState(seed.gapId)
    if (retryState.unresolvable) {
      flags.push('max_retries_reached')
      this.activeFlags.add('max_retries_reached')
      return this.makeResult(seed.id, seed.gapId, 'defer', flags, 'Gap marked as unresolvable')
    }
    if (retryState.retryCount >= this.config.maxRetriesPerGap) {
      flags.push('max_retries_reached')
      this.activeFlags.add('max_retries_reached')
      this.markGapUnresolvable(seed.gapId)
      return this.makeResult(seed.id, seed.gapId, 'defer', flags, `Max retries reached (${this.config.maxRetriesPerGap}), marking unresolvable`)
    }

    // Check cooldown
    if (retryState.lastAttemptAt) {
      const lastAttempt = new Date(retryState.lastAttemptAt).getTime()
      const cooldownMs = this.config.cooldownHours * 60 * 60 * 1000
      if (Date.now() - lastAttempt < cooldownMs) {
        flags.push('cooldown_active')
        this.activeFlags.add('cooldown_active')
        return this.makeResult(seed.id, seed.gapId, 'defer', flags, `Cooldown active for ${this.config.cooldownHours}h since last attempt`)
      }
    }

    // Risk assessment — high-priority gaps are flagged for review
    if (meta.priority >= this.config.highRiskPriorityThreshold) {
      flags.push('high_risk')
      this.activeFlags.add('high_risk')
      this.persistDecision(seed.id, seed.gapId, 'flag_for_review', flags, `High-priority gap (${meta.priority.toFixed(2)}) requires human review`)
      return this.makeResult(seed.id, seed.gapId, 'flag_for_review', flags, `High-priority gap (${meta.priority.toFixed(2)}) requires human review`)
    }

    // All checks passed — auto-schedule
    const now = new Date().toISOString()
    this.persistDecision(seed.id, seed.gapId, 'auto_schedule', flags, 'Within budget, low risk, auto-scheduled')
    return this.makeResult(seed.id, seed.gapId, 'auto_schedule', flags, 'Within budget, low risk, auto-scheduled', now)
  }

  /**
   * Check the anxious-loop guard (C1.W5).
   *
   * If the fraction of directed meditations within the recent window exceeds
   * the configured threshold, the system is doing too much self-curing.
   * The constraint says: "there is no condition under which the system should
   * be doing more self-curing than living-and-responding."
   */
  private checkAnxiousLoop(totalMeditationCount: number, directedMeditationCount: number): boolean {
    const window = this.config.anxiousLoopWindow
    if (totalMeditationCount < window) {
      // Not enough data to make a reliable determination
      return false
    }

    const fraction = directedMeditationCount / totalMeditationCount
    if (fraction > this.config.anxiousLoopFraction) {
      this.logger.warn('Anxious-loop guard triggered', {
        fraction: fraction.toFixed(2),
        threshold: this.config.anxiousLoopFraction,
        directed: directedMeditationCount,
        total: totalMeditationCount,
      })
      return true
    }

    return false
  }



  private persistDecision(
    seedId: string,
    gapId: string,
    decision: SchedulingDecision,
    flags: SchedulerFlag[],
    reason: string,
  ): void {
    const id = `sched_${crypto.randomUUID().slice(0, 12)}`
    this.stmtInsertDecision.run(id, seedId, gapId, decision, JSON.stringify(flags), reason)
    this.logger.debug('Scheduling decision persisted', { id, seedId, gapId, decision, flags })
  }

  private getOrCreateDailyBudget(date: string): DailyBudgetState {
    const row = this.stmtGetDailyBudget.get(date) as BudgetRow | undefined
    if (row) {
      return {
        date: row.date,
        autoScheduled: row.auto_scheduled,
        costUsd: row.cost_usd,
        perCategory: JSON.parse(row.per_category),
      }
    }

    const empty: DailyBudgetState = { date, autoScheduled: 0, costUsd: 0, perCategory: {} }
    this.persistDailyBudget(date, empty)
    return empty
  }

  private persistDailyBudget(date: string, budget: DailyBudgetState): void {
    this.stmtUpsertDailyBudget.run(
      date,
      budget.autoScheduled,
      budget.costUsd,
      JSON.stringify(budget.perCategory),
    )
  }

  private recordRetry(gapId: string): void {
    const now = new Date().toISOString()
    const existing = this.stmtGetRetry.get(gapId) as RetryRow | undefined
    if (existing) {
      this.stmtIncrementRetry.run(now, gapId)
    } else {
      this.stmtUpsertRetry.run(gapId, 1, now)
    }
  }

  private markGapUnresolvable(gapId: string): void {
    const now = new Date().toISOString()
    this.stmtMarkUnresolvable.run(now, gapId)
    this.logger.info('Gap marked as unresolvable after max retries', { gapId, maxRetries: this.config.maxRetriesPerGap })
  }

  private countTodayDecisions(decision: string): number {
    const today = this.todayStr()
    const rows = this.db.prepare(
      `SELECT COUNT(*) as cnt FROM scheduling_decisions WHERE decision = ? AND created_at >= ?`,
    ).get(decision, `${today}T00:00:00.000Z`) as { cnt: number } | undefined
    return rows?.cnt ?? 0
  }

  private makeResult(
    seedId: string,
    gapId: string,
    decision: SchedulingDecision,
    flags: SchedulerFlag[],
    reason: string,
    scheduledAt: string | null = null,
  ): SchedulingResult {
    return { seedId, gapId, decision, flags, reason, scheduledAt }
  }

  private todayStr(): string {
    return new Date().toISOString().slice(0, 10)
  }



  private initSchema(): void {
    this.db.exec('CREATE TABLE IF NOT EXISTS scheduler_schema_version (version INTEGER PRIMARY KEY)')
    const current = this.db.prepare('SELECT version FROM scheduler_schema_version').get() as { version: number } | undefined
    if (!current) {
      this.db.exec(SCHEMA_V1)
    }
  }

  private prepareStatements(): void {
    this.stmtInsertDecision = this.db.prepare(
      `INSERT INTO scheduling_decisions (id, seed_id, gap_id, decision, flags, reason, scheduled_at)
       VALUES (?, ?, ?, ?, ?, ?, NULL)`,
    )
    this.stmtGetDecisionsByGap = this.db.prepare(
      `SELECT * FROM scheduling_decisions WHERE gap_id = ? ORDER BY created_at DESC`,
    )
    this.stmtGetDailyBudget = this.db.prepare(
      `SELECT * FROM daily_budget WHERE date = ?`,
    )
    this.stmtUpsertDailyBudget = this.db.prepare(
      `INSERT INTO daily_budget (date, auto_scheduled, cost_usd, per_category) VALUES (?, ?, ?, ?)
       ON CONFLICT(date) DO UPDATE SET auto_scheduled = excluded.auto_scheduled, cost_usd = excluded.cost_usd, per_category = excluded.per_category`,
    )
    this.stmtGetRetry = this.db.prepare(
      `SELECT * FROM gap_retry_tracking WHERE gap_id = ?`,
    )
    this.stmtUpsertRetry = this.db.prepare(
      `INSERT INTO gap_retry_tracking (gap_id, retry_count, last_attempt_at) VALUES (?, ?, ?)
       ON CONFLICT(gap_id) DO UPDATE SET retry_count = excluded.retry_count, last_attempt_at = excluded.last_attempt_at`,
    )
    this.stmtIncrementRetry = this.db.prepare(
      `UPDATE gap_retry_tracking SET retry_count = retry_count + 1, last_attempt_at = ? WHERE gap_id = ?`,
    )
    this.stmtMarkUnresolvable = this.db.prepare(
      `UPDATE gap_retry_tracking SET marked_unresolvable_at = ? WHERE gap_id = ?`,
    )
  }
}



/** Create an AutoScheduler with the default data directory path. */
export function createAutoScheduler(
  config: Partial<AutoSchedulerConfig> = {},
  logger: ILogger,
): AutoScheduler {
  const dbPath = path.join(getDataDir(), 'system-state.db')
  return new AutoScheduler(dbPath, config, logger)
}
