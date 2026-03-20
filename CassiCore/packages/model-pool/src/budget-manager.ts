/**
 * Budget Manager - Hierarchical Budget Tracking for ModelPool
 */

import { BillingModel, type BudgetScope, type BudgetLimits, type BudgetWarning, type BudgetTier } from './types.js'
import type { ILogger, IEventBus } from '../../types/interfaces.js'

/**
 * Result of a budget check.
 */
export interface BudgetStatus {
  allowed: boolean
  remaining: number
  limit?: number
  percentUsed: number
  warnings: BudgetWarning[]
  reason?: string
}

/**
 * Usage tracking data for a single request.
 */
export interface UsageData {
  inputTokens: number
  outputTokens: number
  requests: number
}

/**
 * Hierarchical budget manager for ModelPool.
 */
export class BudgetManager {
  private readonly logger: ILogger
  private readonly eventBus: IEventBus
  private readonly scopes: Map<string, BudgetScope>
  private readonly warningThresholds: number[]
  private readonly previousTiers: Map<string, BudgetTier>

  constructor(
    eventBus: IEventBus,
    logger: ILogger,
    warningThresholds: number[] = [50, 75, 90],
  ) {
    this.eventBus = eventBus
    this.logger = logger.child('budget-manager')
    this.scopes = new Map()
    this.warningThresholds = warningThresholds.sort((a, b) => a - b)
    this.previousTiers = new Map()
  }

  /**
   * Create a new budget scope.
   */
  createScope(
    id: string,
    name: string,
    type: 'team' | 'session' | 'slot' | 'provider',
    limits: BudgetLimits,
    billingModel: BillingModel,
    parentId?: string,
  ): BudgetScope {
    if (this.scopes.has(id)) {
      throw new Error(`Budget scope already exists: ${id}`)
    }

    const scope: BudgetScope = {
      id,
      parentId,
      name,
      type,
      limits,
      billingModel,
      used: {
        requests: 0,
        tokens: 0,
        inputTokens: 0,
        outputTokens: 0,
        lastUpdated: new Date(),
      },
    }

    this.scopes.set(id, scope)
    this.previousTiers.set(id, 'normal')
    this.logger.debug('Created budget scope', { id, name, type, billingModel })

    return scope
  }

  /**
   * Get a budget scope by ID.
   */
  getScope(id: string): BudgetScope | undefined {
    return this.scopes.get(id)
  }

  /**
   * Check budget status for a scope (tracking and warnings only — never denies requests).
   */
  checkBudget(scopeId: string): BudgetStatus {
    const scope = this.scopes.get(scopeId)
    if (!scope) {
      // If no scopes are configured at all, budget is unlimited.
      // If scopes exist but this one wasn't registered, still allow — just warn.
      if (this.scopes.size > 0) {
        this.logger.warn('Budget scope not found — allowing request (tracking only)', { scopeId })
      }
      return {
        allowed: true,
        remaining: Infinity,
        percentUsed: 0,
        warnings: [],
      }
    }

    const warnings: BudgetWarning[] = []
    const scopeChain = this.getScopeChain(scope)

    for (const s of scopeChain) {
      const status = this.checkSingleScope(s)
      warnings.push(...status.warnings)
    }

    const mostRestrictive = scopeChain.reduce((min, s) => {
      const status = this.checkSingleScope(s)
      return status.remaining < min.remaining ? status : min
    }, this.checkSingleScope(scope))

    return {
      allowed: true,
      remaining: mostRestrictive.remaining,
      limit: mostRestrictive.limit,
      percentUsed: mostRestrictive.percentUsed,
      warnings,
    }
  }

  /**
   * Track usage for a budget scope.
   */
  async trackUsage(scopeId: string, usage: UsageData): Promise<BudgetWarning[]> {
    const scope = this.scopes.get(scopeId)
    if (!scope) {
      this.logger.warn('Cannot track usage for unknown scope', { scopeId })
      return []
    }

    const scopeChain = this.getScopeChain(scope)
    const allWarnings: BudgetWarning[] = []

    for (const s of scopeChain) {
      s.used.requests += usage.requests
      s.used.tokens += usage.inputTokens + usage.outputTokens
      s.used.inputTokens += usage.inputTokens
      s.used.outputTokens += usage.outputTokens
      s.used.lastUpdated = new Date()

      const warnings = await this.checkThresholds(s)
      allWarnings.push(...warnings)
    }

    return allWarnings
  }

  /**
   * Get the current tier for a scope.
   */
  getTier(scopeId: string): BudgetTier {
    const status = this.checkBudget(scopeId)
    return this.getTierForPercentUsed(status.percentUsed)
  }

  /**
   * Reset usage for a budget scope.
   */
  resetUsage(scopeId: string): void {
    const scope = this.scopes.get(scopeId)
    if (!scope) {
      this.logger.warn('Cannot reset unknown scope', { scopeId })
      return
    }

    scope.used = {
      requests: 0,
      tokens: 0,
      inputTokens: 0,
      outputTokens: 0,
      lastUpdated: new Date(),
    }

    this.previousTiers.set(scopeId, 'normal')
    this.logger.info('Reset budget usage', { scopeId })
  }

  /**
   * Dispose of the BudgetManager and clean up resources.
   */
  dispose(): void {
    this.scopes.clear()
    this.previousTiers.clear()
    this.logger.info('BudgetManager disposed')
  }

  // Private Methods

  private getScopeChain(scope: BudgetScope): BudgetScope[] {
    const chain: BudgetScope[] = []
    let current: BudgetScope | undefined = scope

    while (current) {
      chain.unshift(current)
      if (current.parentId) {
        current = this.scopes.get(current.parentId)
      } else {
        current = undefined
      }
    }

    return chain
  }

  private checkSingleScope(scope: BudgetScope): BudgetStatus {
    const percentUsed = this.calculatePercentUsed(scope)
    const warnings: BudgetWarning[] = []

    // Budget exceeded — warn but never deny
    if (percentUsed >= 100) {
      this.logger.warn('Budget exceeded in scope — continuing (tracking only)', {
        scopeId: scope.id,
        percentUsed,
        limit: this.getLimit(scope),
      })
    }

    const tier = this.getTierForPercentUsed(percentUsed)

    for (const threshold of this.warningThresholds) {
      if (percentUsed >= threshold) {
        // Only include warnings for non-normal tiers
        if (tier !== 'normal') {
          warnings.push({
            scopeId: scope.id,
            tier: tier as 'cautious' | 'frugal' | 'critical',
            threshold,
            percentUsed,
            projectedExhaustion: this.projectExhaustion(scope),
          })
        }
      }
    }

    return {
      allowed: true,
      remaining: this.calculateRemaining(scope),
      limit: this.getLimit(scope),
      percentUsed,
      warnings,
    }
  }

  private async checkThresholds(scope: BudgetScope): Promise<BudgetWarning[]> {
    const percentUsed = this.calculatePercentUsed(scope)
    const currentTier = this.getTierForPercentUsed(percentUsed)
    const previousTier = this.previousTiers.get(scope.id) || 'normal'
    const warnings: BudgetWarning[] = []

    if (currentTier !== previousTier) {
      const remaining = this.calculateRemaining(scope)
      const limit = this.getLimit(scope)

      await this.eventBus.emit({
        type: 'budget:tier_changed',
        providerId: scope.id,
        previousTier,
        newTier: currentTier,
        percentUsed,
        remaining,
        timestamp: new Date(),
      })

      this.previousTiers.set(scope.id, currentTier)
      this.logger.info('Budget tier changed', {
        scopeId: scope.id,
        previousTier,
        newTier: currentTier,
        percentUsed,
      })
    }

    for (const threshold of this.warningThresholds) {
      if (percentUsed >= threshold) {
        const tier = this.getTierForThreshold(threshold)
        const warning: BudgetWarning = {
          scopeId: scope.id,
          tier,
          threshold,
          percentUsed,
          projectedExhaustion: this.projectExhaustion(scope),
        }
        warnings.push(warning)

        // Emit budget:warning event matching RuntimeEvent type
        await this.eventBus.emit({
          type: 'budget:warning',
          providerId: scope.id,
          tier,
          percentUsed,
          remaining: this.calculateRemaining(scope),
          monthlyLimit: this.getLimit(scope),
          timestamp: new Date(),
        })
      }
    }

    if (percentUsed >= 100) {
      // Emit budget:tier_changed to indicate exhaustion (critical tier)
      await this.eventBus.emit({
        type: 'budget:tier_changed',
        providerId: scope.id,
        previousTier,
        newTier: 'critical',
        percentUsed,
        remaining: 0,
        timestamp: new Date(),
      })

      this.logger.warn('Budget exhausted', {
        scopeId: scope.id,
        percentUsed,
        limit: this.getLimit(scope),
      })
    }

    return warnings
  }

  private getTierForThreshold(threshold: number): 'cautious' | 'frugal' | 'critical' {
    if (threshold >= 90) return 'critical'
    if (threshold >= 75) return 'frugal'
    return 'cautious'
  }

  private getTierForPercentUsed(percentUsed: number): BudgetTier {
    if (percentUsed >= 95) return 'critical'
    if (percentUsed >= 85) return 'frugal'
    if (percentUsed >= 70) return 'cautious'
    return 'normal'
  }

  private calculatePercentUsed(scope: BudgetScope): number {
    const { limits, used, billingModel } = scope

    if (billingModel === BillingModel.GITHUB_COPILOT || billingModel === BillingModel.ALIBABA_CODING) {
      if (limits.maxRequests !== undefined && limits.maxRequests > 0) {
        return (used.requests / limits.maxRequests) * 100
      }
    } else if (billingModel === BillingModel.TOKEN_BASED) {
      if (limits.maxTokens !== undefined && limits.maxTokens > 0) {
        return (used.tokens / limits.maxTokens) * 100
      }
    }

    return 0
  }

  private projectExhaustion(scope: BudgetScope): Date | undefined {
    const percentUsed = this.calculatePercentUsed(scope)

    if (percentUsed <= 0 || percentUsed >= 100) {
      return undefined
    }

    const now = new Date()
    const timeSinceUpdate = now.getTime() - scope.used.lastUpdated.getTime()

    if (timeSinceUpdate <= 0) {
      return undefined
    }

    const timeToExhaustion = (timeSinceUpdate / percentUsed) * (100 - percentUsed)
    return new Date(now.getTime() + timeToExhaustion)
  }

  private calculateRemaining(scope: BudgetScope): number {
    const { limits, used, billingModel } = scope

    if (billingModel === BillingModel.GITHUB_COPILOT || billingModel === BillingModel.ALIBABA_CODING) {
      if (limits.maxRequests !== undefined) {
        return Math.max(0, limits.maxRequests - used.requests)
      }
    } else if (billingModel === BillingModel.TOKEN_BASED) {
      if (limits.maxTokens !== undefined) {
        return Math.max(0, limits.maxTokens - used.tokens)
      }
    }

    return 0
  }

  private getLimit(scope: BudgetScope): number {
    const { limits, billingModel } = scope

    if (billingModel === BillingModel.GITHUB_COPILOT || billingModel === BillingModel.ALIBABA_CODING) {
      return limits.maxRequests || 0
    } else if (billingModel === BillingModel.TOKEN_BASED) {
      return limits.maxTokens || 0
    }

    return 0
  }
}
