/**
 * CorpusStrategyRegistry — Registry for workflow-dispatched coordination strategies.
 *
 * WHY: The Corpus async loop detects cross-branch patterns but acts on them with
 * inline imperative code. The registry decouples pattern detection from response,
 * letting strategies be registered, prioritized, and dispatched as workflows.
 *
 * HOW: Strategies register with pattern types and a match predicate. When the Corpus
 * detects a pattern, the registry finds the highest-priority matching strategy and
 * returns it. The Corpus then builds and executes the strategy's workflow.
 */

import type { ILogger } from './vendor/types/interfaces.js'
import type {
  CorpusStrategy,
  CrossHelixPattern,
  CrossHelixPatternType,
  CorpusProcessedState,
  ActiveStrategyRun,
} from './corpus-types.js'

export class CorpusStrategyRegistry {
  private strategies: Map<string, CorpusStrategy> = new Map()
  private patternIndex: Map<CrossHelixPatternType, CorpusStrategy[]> = new Map()
  private activeRuns: Map<string, ActiveStrategyRun> = new Map()
  private logger: ILogger

  constructor(logger: ILogger) {
    this.logger = logger.child('CorpusStrategyRegistry')
  }

  /**
   * Register a strategy. Replaces any existing strategy with the same id.
   */
  register(strategy: CorpusStrategy): void {
    this.strategies.set(strategy.id, strategy)

    for (const patternType of strategy.patternTypes) {
      const existing = this.patternIndex.get(patternType) ?? []
      const filtered = existing.filter(s => s.id !== strategy.id)
      filtered.push(strategy)
      filtered.sort((a, b) => b.priority - a.priority)
      this.patternIndex.set(patternType, filtered)
    }

    this.logger.info('Strategy registered', {
      id: strategy.id,
      patternTypes: strategy.patternTypes,
      priority: strategy.priority,
    })
  }

  /**
   * Unregister a strategy by id.
   */
  unregister(id: string): boolean {
    const strategy = this.strategies.get(id)
    if (!strategy) return false

    this.strategies.delete(id)

    for (const patternType of strategy.patternTypes) {
      const existing = this.patternIndex.get(patternType) ?? []
      const filtered = existing.filter(s => s.id !== id)
      if (filtered.length > 0) {
        this.patternIndex.set(patternType, filtered)
      } else {
        this.patternIndex.delete(patternType)
      }
    }

    this.logger.info('Strategy unregistered', { id })
    return true
  }

  /**
   * Find the highest-priority strategy that matches a given pattern.
   *
   * HOW: First filters by patternTypes (fast index lookup), then calls
   * each strategy's matches() predicate in priority order. Returns the
   * first match or null.
   */
  match(pattern: CrossHelixPattern, state: CorpusProcessedState): CorpusStrategy | null {
    const candidates = this.patternIndex.get(pattern.type)
    if (!candidates || candidates.length === 0) return null

    for (const strategy of candidates) {
      try {
        if (strategy.matches(pattern, state)) {
          return strategy
        }
      } catch (err) {
        this.logger.warn('Strategy match() threw', {
          strategyId: strategy.id,
          patternType: pattern.type,
          error: String(err),
        })
      }
    }

    return null
  }

  /**
   * Track an active strategy workflow run.
   */
  trackRun(run: ActiveStrategyRun): void {
    this.activeRuns.set(run.runId, run)
    this.logger.debug('Strategy run tracked', {
      runId: run.runId,
      strategyId: run.strategyId,
      patternType: run.pattern.type,
    })
  }

  /**
   * Complete a tracked run with its result.
   */
  completeRun(runId: string, result: ActiveStrategyRun['result']): void {
    const run = this.activeRuns.get(runId)
    if (run) {
      run.result = result
      this.logger.info('Strategy run completed', {
        runId,
        strategyId: run.strategyId,
        status: result?.status,
        durationMs: result?.durationMs,
      })
    }
  }

  /**
   * Remove a tracked run (after processing its result).
   */
  removeRun(runId: string): void {
    this.activeRuns.delete(runId)
  }

  /**
   * Get all active (incomplete) strategy runs.
   */
  getActiveRuns(): ActiveStrategyRun[] {
    return [...this.activeRuns.values()].filter(r => !r.result)
  }

  /**
   * Get all tracked runs (active + completed).
   */
  getAllRuns(): ActiveStrategyRun[] {
    return [...this.activeRuns.values()]
  }

  /**
   * Check if a strategy is already running for a given pattern.
   * Prevents duplicate dispatches for the same pattern.
   */
  isRunningForPattern(pattern: CrossHelixPattern): boolean {
    for (const run of this.activeRuns.values()) {
      if (run.result) continue
      if (run.pattern.type === pattern.type &&
          run.pattern.helixIds.every(id => pattern.helixIds.includes(id))) {
        return true
      }
    }
    return false
  }

  /**
   * List all registered strategies.
   */
  list(): CorpusStrategy[] {
    return [...this.strategies.values()]
  }

  /**
   * Get a strategy by id.
   */
  get(id: string): CorpusStrategy | undefined {
    return this.strategies.get(id)
  }

  /**
   * Number of registered strategies.
   */
  get size(): number {
    return this.strategies.size
  }
}
