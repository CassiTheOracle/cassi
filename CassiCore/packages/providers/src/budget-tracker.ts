/**
 * Budget Tracker — Persistent monthly request budget for metered providers.
 *
 * Tracks request counts per provider per calendar month. Provides usage
 * percentages, daily burn rates, and projected exhaustion dates so the
 * ModelRouter can make informed decisions about where to send requests.
 *
 * Design:
 * - Persists across daemon restarts via JSON file (~/.cassicore/budget-state.json)
 * - Automatic month rollover (compares YYYY-MM)
 * - Thread-safe (single-writer via daemon main process)
 * - Integrates with EventBus provider:request_end events
 * - Emits budget:warning and budget:tier_changed events on tier transitions
 */

import { homedir } from 'node:os'
import { join } from 'node:path'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import type { ILogger, IEventBus } from '../../types/interfaces.js'
import type { RequestCost } from './cost-classifier.js'
import { getCostClassifier } from './cost-classifier.js'

// ─── Types ───────────────────────────────────────────────────────────────────

export interface ProviderBudgetConfig {
  /** Monthly request limit (e.g., 1500 for github-copilot) */
  monthlyLimit: number
}

export interface BudgetSnapshot {
  providerId: string
  monthlyLimit: number
  currentMonth: string
  used: number
  remaining: number
  percentUsed: number
  /** Average metered requests per day this month */
  dailyBurnRate: number
  /** Projected day-of-month when budget exhausts (null if sustainable) */
  projectedExhaustionDay: number | null
}

/**
 * Budget usage tiers for adaptive behavior.
 * - 'normal'   (0-50%)   — all modules active
 * - 'cautious' (50-75%)  — background tasks prefer free models
 * - 'frugal'   (75-90%)  — non-essential background tasks disabled
 * - 'critical' (90-100%) — only user-facing turns use metered models
 */
export type BudgetTier = 'normal' | 'cautious' | 'frugal' | 'critical'

export const BUDGET_TIER_THRESHOLDS = {
  normal:   0.50,
  cautious: 0.75,
  frugal:   0.90,
  critical: 1.00,
} as const

// ─── Default Budgets ─────────────────────────────────────────────────────────

export const DEFAULT_PROVIDER_BUDGETS: Record<string, ProviderBudgetConfig> = {
  'github-copilot': { monthlyLimit: 1500 },
}

// ─── Persistence Path ────────────────────────────────────────────────────────

const BUDGET_STATE_PATH = join(homedir(), '.cassicore', 'budget-state.json')

// ─── Budget Tracker ──────────────────────────────────────────────────────────

export class BudgetTracker {
  private readonly logger: ILogger
  private readonly budgets: Record<string, ProviderBudgetConfig>
  private readonly classifier = getCostClassifier()

  /**
   * In-memory counters: providerId → { month: 'YYYY-MM', count: number, dailyCounts: Map<day, count> }
   * Persisted to JSON file on shutdown, loaded on startup.
   */
  private readonly counters = new Map<string, {
    month: string
    count: number
    /** Per-day breakdown for burn rate calculation: day-of-month → count */
    dailyCounts: Map<number, number>
    /** First recorded request timestamp this month */
    firstRequestAt: number
  }>()

  /** Tracks the last-known tier per provider so we can detect transitions */
  private readonly previousTiers = new Map<string, BudgetTier>()

  private bus: IEventBus | undefined

  constructor(
    logger: ILogger,
    budgets?: Record<string, ProviderBudgetConfig>,
  ) {
    this.logger = (typeof (logger as any).child === 'function') ? (logger as any).child('budget-tracker') : logger
    this.budgets = budgets ?? DEFAULT_PROVIDER_BUDGETS
  }

  // ── EventBus Integration ─────────────────────────────────────────────────

  /**
   * Wire up to the EventBus to automatically track provider requests.
   * Listens for provider:request_end events and increments counters
   * for metered models.
   */
  wire(bus: IEventBus): void {
    this.bus = bus
    bus.on('provider:request_end', (event: any) => {
      const { providerId, sessionId } = event
      // Reconstruct the full model spec — we need providerId + model
      // The event carries providerId and we need to check if this specific
      // request was metered. Since we don't have the model in the event,
      // we record all requests for providers that have budgets configured.
      if (this.budgets[providerId]) {
        // Check if this provider uses request-based billing by looking at
        // whether it has a budget entry. Only count if it's not a free model.
        // Since we can't determine the exact model from the event alone,
        // we rely on the caller to use recordRequest() directly for model-level
        // classification. Here we just count all requests for budgeted providers
        // as a conservative upper bound.
        this.recordProviderRequest(providerId)
      }
    })
    this.logger.info('BudgetTracker wired to EventBus')
  }

  // ── Recording ────────────────────────────────────────────────────────────

  /**
   * Record a metered request for a specific provider/model combination.
   * Only increments the counter if the model is classified as 'metered'.
   *
   * Call this from the CentralizedProvider after a successful request.
   */
  recordRequest(providerModel: string): void {
    const cost = this.classifier.classify(providerModel)
    if (cost !== 'metered') return

    const providerId = providerModel.split('/')[0]
    if (!this.budgets[providerId]) return

    this.recordProviderRequest(providerId)
  }

  /**
   * Record a request directly for a provider (bypasses model classification).
   */
  private recordProviderRequest(providerId: string): void {
    const month = getCurrentMonth()
    const day = new Date().getDate()

    let counter = this.counters.get(providerId)
    if (!counter || counter.month !== month) {
      // New month — reset counter
      counter = { month, count: 0, dailyCounts: new Map(), firstRequestAt: Date.now() }
      this.counters.set(providerId, counter)
    }

    counter.count++
    counter.dailyCounts.set(day, (counter.dailyCounts.get(day) ?? 0) + 1)
    this.checkThresholds(providerId)
  }

  // ── Queries ──────────────────────────────────────────────────────────────

  /**
   * Get the current budget snapshot for a provider.
   */
  getSnapshot(providerId: string): BudgetSnapshot | null {
    const config = this.budgets[providerId]
    if (!config) return null

    const month = getCurrentMonth()
    const counter = this.counters.get(providerId)
    const used = (counter && counter.month === month) ? counter.count : 0
    const remaining = Math.max(0, config.monthlyLimit - used)
    const percentUsed = config.monthlyLimit > 0 ? used / config.monthlyLimit : 0

    // Calculate daily burn rate
    const dailyBurnRate = this.calculateDailyBurnRate(providerId)

    // Project exhaustion day
    let projectedExhaustionDay: number | null = null
    if (dailyBurnRate > 0) {
      const daysRemaining = remaining / dailyBurnRate
      const today = new Date().getDate()
      const daysInMonth = new Date(new Date().getFullYear(), new Date().getMonth() + 1, 0).getDate()
      const exhaustionDay = today + daysRemaining
      if (exhaustionDay <= daysInMonth) {
        projectedExhaustionDay = Math.ceil(exhaustionDay)
      }
    }

    return {
      providerId,
      monthlyLimit: config.monthlyLimit,
      currentMonth: month,
      used,
      remaining,
      percentUsed,
      dailyBurnRate,
      projectedExhaustionDay,
    }
  }

  /**
   * Get the remaining request count for a provider.
   */
  getRemaining(providerId: string): number {
    return this.getSnapshot(providerId)?.remaining ?? Infinity
  }

  /**
   * Get the current usage percentage (0-1) for a provider.
   */
  getUsagePercent(providerId: string): number {
    return this.getSnapshot(providerId)?.percentUsed ?? 0
  }

  /**
   * Get the current budget tier for a provider.
   */
  getTier(providerId: string): BudgetTier {
    const percent = this.getUsagePercent(providerId)
    if (percent >= BUDGET_TIER_THRESHOLDS.frugal) return 'critical'
    if (percent >= BUDGET_TIER_THRESHOLDS.cautious) return 'frugal'
    if (percent >= BUDGET_TIER_THRESHOLDS.normal) return 'cautious'
    return 'normal'
  }

  /**
   * Check if a specific provider/model request should be allowed.
   * Returns true if the request is free/local OR within budget.
   */
  canAfford(providerModel: string): boolean {
    const cost = this.classifier.classify(providerModel)
    if (cost === 'free' || cost === 'local') return true

    const providerId = providerModel.split('/')[0]
    return this.getRemaining(providerId) > 0
  }

  /**
   * Get snapshots for all configured providers.
   */
  getAllSnapshots(): BudgetSnapshot[] {
    return Object.keys(this.budgets).map(id => this.getSnapshot(id)).filter(Boolean) as BudgetSnapshot[]
  }

  /**
   * Emit budget events when thresholds are crossed or tier transitions occur.
   * Call this after recording a request.
   */
  private checkThresholds(providerId: string): void {
    if (!this.bus) return

    const snapshot = this.getSnapshot(providerId)
    if (!snapshot) return

    const newTier = this.getTier(providerId)
    const previousTier = this.previousTiers.get(providerId) ?? 'normal'

    // Detect tier transition
    if (newTier !== previousTier) {
      this.previousTiers.set(providerId, newTier)
      this.bus.emit({
        type: 'budget:tier_changed',
        providerId,
        previousTier,
        newTier,
        percentUsed: snapshot.percentUsed,
        remaining: snapshot.remaining,
      })
      this.logger.warn('Budget tier changed', {
        providerId,
        previousTier,
        newTier,
        percentUsed: Math.round(snapshot.percentUsed),
        remaining: snapshot.remaining,
      })
    }

    // Emit warning for non-normal tiers (every request while in warning zone)
    if (newTier === 'cautious' || newTier === 'frugal' || newTier === 'critical') {
      this.bus.emit({
        type: 'budget:warning',
        providerId,
        tier: newTier,
        percentUsed: snapshot.percentUsed,
        remaining: snapshot.remaining,
        monthlyLimit: snapshot.monthlyLimit,
      })
    }
  }

  // ── Persistence ──────────────────────────────────────────────────────────

  /**
   * Export current state for persistence (e.g., to SQLite or JSON).
   */
  exportState(): Record<string, { month: string; count: number; dailyCounts: Record<number, number> }> {
    const state: Record<string, { month: string; count: number; dailyCounts: Record<number, number> }> = {}
    for (const [providerId, counter] of this.counters) {
      state[providerId] = {
        month: counter.month,
        count: counter.count,
        dailyCounts: Object.fromEntries(counter.dailyCounts),
      }
    }
    return state
  }

  /**
   * Import previously persisted state (e.g., on daemon startup).
   */
  importState(state: Record<string, { month: string; count: number; dailyCounts?: Record<number | string, number> }>): void {
    const currentMonth = getCurrentMonth()
    for (const [providerId, data] of Object.entries(state)) {
      // Only import if same month — stale data from previous months is irrelevant
      if (data.month !== currentMonth) continue

      const dailyCounts = new Map<number, number>()
      if (data.dailyCounts) {
        for (const [day, count] of Object.entries(data.dailyCounts)) {
          dailyCounts.set(Number(day), count)
        }
      }

      this.counters.set(providerId, {
        month: data.month,
        count: data.count,
        dailyCounts,
        firstRequestAt: Date.now(),
      })

      // Initialize previousTiers so we don't emit a false transition on first request
      this.previousTiers.set(providerId, this.getTier(providerId))
    }
    this.logger.info('BudgetTracker state imported', {
      providers: Object.keys(state),
      currentMonth,
    })
  }

  /**
   * Save budget state to disk (~/.cassicore/budget-state.json).
   * Called on daemon shutdown to preserve counters across restarts.
   */
  async saveToDisk(): Promise<void> {
    try {
      const state = this.exportState()
      if (Object.keys(state).length === 0) {
        this.logger.debug('BudgetTracker: no state to persist')
        return
      }
      const dir = join(homedir(), '.cassicore')
      await mkdir(dir, { recursive: true })
      await writeFile(BUDGET_STATE_PATH, JSON.stringify(state, null, 2), 'utf-8')
      this.logger.info('BudgetTracker state saved to disk', {
        path: BUDGET_STATE_PATH,
        providers: Object.keys(state),
      })
    } catch (err) {
      this.logger.error('Failed to save BudgetTracker state', { error: String(err) })
    }
  }

  /**
   * Load budget state from disk (~/.cassicore/budget-state.json).
   * Called on daemon startup to restore counters from previous session.
   * Stale months are automatically discarded by importState().
   */
  async loadFromDisk(): Promise<void> {
    try {
      const raw = await readFile(BUDGET_STATE_PATH, 'utf-8')
      const state = JSON.parse(raw)
      this.importState(state)
      this.logger.info('BudgetTracker state loaded from disk', {
        path: BUDGET_STATE_PATH,
      })
    } catch (err: unknown) {
      // ENOENT is expected on first run — don't log as error
      if ((err as NodeJS.ErrnoException).code === 'ENOENT') {
        this.logger.debug('No budget state file found (first run)')
        return
      }
      this.logger.warn('Failed to load BudgetTracker state from disk', { error: String(err) })
    }
  }

  // ── Internal ─────────────────────────────────────────────────────────────

  private calculateDailyBurnRate(providerId: string): number {
    const month = getCurrentMonth()
    const counter = this.counters.get(providerId)
    if (!counter || counter.month !== month) return 0

    const dailyCounts = Array.from(counter.dailyCounts.values())
    if (dailyCounts.length === 0) return 0

    // Use the average of all days with activity
    const total = dailyCounts.reduce((sum, c) => sum + c, 0)
    return total / dailyCounts.length
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getCurrentMonth(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

// ─── Singleton ───────────────────────────────────────────────────────────────

let _defaultTracker: BudgetTracker | undefined

export function getBudgetTracker(logger?: ILogger): BudgetTracker {
  if (!_defaultTracker) {
    if (!logger) throw new Error('BudgetTracker not initialized — provide a logger on first call')
    _defaultTracker = new BudgetTracker(logger)
  }
  return _defaultTracker
}

export function createBudgetTracker(
  logger: ILogger,
  budgets?: Record<string, ProviderBudgetConfig>,
): BudgetTracker {
  _defaultTracker = new BudgetTracker(logger, budgets)
  return _defaultTracker
}
