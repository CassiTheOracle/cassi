/**
 * Billing Models - Classification and Request Counting
 *
 * Provides billing model classification and request counting strategies
 * for different provider types. Integrates with existing CostClassifier
 * and BudgetTracker.
 *
 * Key distinction from CostClassifier:
 * - CostClassifier: broad categories ('free' | 'metered' | 'local')
 * - BillingModel: specific billing systems ('github-copilot', 'token-based', etc.)
 *
 * All imports use .js extensions (TypeScript ESM).
 */

import { CostClassifier, type RequestCost } from '../providers/cost-classifier.js'
import { BillingModel } from './types.js'
import type { BudgetScope, BudgetUsage } from './types.js'
import type { ILogger } from '../../types/interfaces.js'

// Request Counter Interface

/**
 * Snapshot of usage for a provider+model combination.
 */
export interface UsageSnapshot {
  /** Provider ID */
  provider: string
  /** Model ID */
  model: string
  /** Billing model for this combination */
  billingModel: BillingModel
  /** Current period usage */
  usage: BudgetUsage
  /** Budget limit (if applicable) */
  limit?: number
  /** Percentage of budget used */
  percentUsed: number
}

/**
 * Request counter interface for tracking usage.
 * Different implementations for different billing models.
 */
export interface RequestCounter {
  /**
   * Record a request with optional token counts.
   */
  recordRequest(
    provider: string,
    model: string,
    tokens?: { input: number; output: number },
  ): void

  /**
   * Get current usage snapshot for a provider+model.
   */
  getUsage(provider: string, model: string): UsageSnapshot

  /**
   * Reset usage counters for a provider+model.
   */
  reset(provider: string, model: string): void

  /**
   * Check if a request would exceed budget limits.
   */
  wouldExceedBudget(
    provider: string,
    model: string,
    estimatedTokens?: { input: number; output: number },
  ): boolean
}

// GitHub Copilot Request Counter (Request-Based Monthly Quota)

/**
 * Request counter for GitHub Copilot billing model.
 * Tracks request counts per calendar month with quota limits.
 */
export class CopilotRequestCounter implements RequestCounter {
  private readonly logger: ILogger
  private readonly monthlyQuota: number
  private readonly freeModels: Set<string>
  private usage: Map<string, { requests: number; resetAt: Date; lastUpdated: Date }>

  constructor(
    logger: ILogger,
    monthlyQuota: number = 1000, // Default monthly request quota
    freeModels: string[] = ['gpt-5-mini'], // Models exempt from quota
  ) {
    this.logger = logger.child('copilot-counter')
    this.monthlyQuota = monthlyQuota
    this.freeModels = new Set(freeModels.map((m) => m.toLowerCase()))
    this.usage = new Map()
  }

  recordRequest(provider: string, model: string, _tokens?: { input: number; output: number }): void {
    // Free models don't count against quota
    if (this.freeModels.has(model.toLowerCase())) {
      this.logger.debug('Free model request (not counted)', { provider, model })
      return
    }

    const key = `${provider}::${model}`
    const now = new Date()
    let record = this.usage.get(key)

    // Reset if new month
    if (!record || now >= record.resetAt) {
      record = {
        requests: 0,
        resetAt: this.getNextMonthStart(now),
        lastUpdated: now,
      }
      this.usage.set(key, record)
    }

    record.requests++
    record.lastUpdated = now
    this.logger.debug('Recorded Copilot request', { provider, model, count: record.requests })
  }

  getUsage(provider: string, model: string): UsageSnapshot {
    const key = `${provider}::${model}`
    const record = this.usage.get(key)
    const now = new Date()

    if (!record || now >= record.resetAt) {
      // No usage or reset period passed
      return {
        provider,
        model,
        billingModel: BillingModel.GITHUB_COPILOT,
        usage: {
          requests: 0,
          tokens: 0,
          inputTokens: 0,
          outputTokens: 0,
          resetAt: this.getNextMonthStart(now),
          lastUpdated: now,
        },
        limit: this.freeModels.has(model.toLowerCase()) ? undefined : this.monthlyQuota,
        percentUsed: 0,
      }
    }

    const isFree = this.freeModels.has(model.toLowerCase())
    const limit = isFree ? undefined : this.monthlyQuota
    const percentUsed = limit ? (record.requests / limit) * 100 : 0

    return {
      provider,
      model,
      billingModel: BillingModel.GITHUB_COPILOT,
      usage: {
        requests: record.requests,
        tokens: record.requests, // For request-based, tokens = requests
        inputTokens: 0,
        outputTokens: 0,
        resetAt: record.resetAt,
        lastUpdated: record.lastUpdated,
      },
      limit,
      percentUsed,
    }
  }

  reset(provider: string, model: string): void {
    const key = `${provider}::${model}`
    this.usage.delete(key)
    this.logger.info('Reset Copilot counter', { provider, model })
  }

  wouldExceedBudget(
    provider: string,
    model: string,
    _estimatedTokens?: { input: number; output: number },
  ): boolean {
    if (this.freeModels.has(model.toLowerCase())) {
      return false // Free models never exceed budget
    }

    const snapshot = this.getUsage(provider, model)
    return snapshot.percentUsed >= 100
  }

  private getNextMonthStart(from: Date): Date {
    const next = new Date(from)
    next.setMonth(next.getMonth() + 1)
    next.setDate(1)
    next.setHours(0, 0, 0, 0)
    return next
  }
}

// Token-Based Request Counter (Pay-Per-Use)

/**
 * Request counter for token-based billing models.
 * Tracks token consumption without hard limits (pay-per-use).
 */
export class TokenRequestCounter implements RequestCounter {
  private readonly logger: ILogger
  private readonly costClassifier: CostClassifier
  private usage: Map<
    string,
    { requests: number; tokens: number; inputTokens: number; outputTokens: number; lastUpdated: Date }
  >

  constructor(logger: ILogger, costClassifier?: CostClassifier) {
    this.logger = logger.child('token-counter')
    this.costClassifier = costClassifier || new CostClassifier()
    this.usage = new Map()
  }

  recordRequest(
    provider: string,
    model: string,
    tokens?: { input: number; output: number },
  ): void {
    const key = `${provider}::${model}`
    const now = new Date()
    let record = this.usage.get(key)

    if (!record) {
      record = { requests: 0, tokens: 0, inputTokens: 0, outputTokens: 0, lastUpdated: now }
      this.usage.set(key, record)
    }

    record.requests++
    if (tokens) {
      record.tokens += tokens.input + tokens.output
      record.inputTokens += tokens.input
      record.outputTokens += tokens.output
    }
    record.lastUpdated = now

    this.logger.debug('Recorded token-based request', {
      provider,
      model,
      requests: record.requests,
      tokens: record.tokens,
    })
  }

  getUsage(provider: string, model: string): UsageSnapshot {
    const key = `${provider}::${model}`
    const record = this.usage.get(key)
    const now = new Date()

    if (!record) {
      return {
        provider,
        model,
        billingModel: BillingModel.TOKEN_BASED,
        usage: {
          requests: 0,
          tokens: 0,
          inputTokens: 0,
          outputTokens: 0,
          lastUpdated: now,
        },
        percentUsed: 0, // No hard limit for token-based
      }
    }

    return {
      provider,
      model,
      billingModel: BillingModel.TOKEN_BASED,
      usage: {
        requests: record.requests,
        tokens: record.tokens,
        inputTokens: record.inputTokens,
        outputTokens: record.outputTokens,
        lastUpdated: record.lastUpdated,
      },
      percentUsed: 0, // No hard limit
    }
  }

  reset(provider: string, model: string): void {
    const key = `${provider}::${model}`
    this.usage.delete(key)
    this.logger.info('Reset token counter', { provider, model })
  }

  wouldExceedBudget(
    _provider: string,
    _model: string,
    _estimatedTokens?: { input: number; output: number },
  ): boolean {
    // Token-based billing has no hard limits
    return false
  }
}

// Alibaba Coding Request Counter (Request-Based Monthly Quota)

/**
 * Request counter for Alibaba Coding billing model.
 * Similar to GitHub Copilot but with separate quota tracking.
 */
export class AlibabaRequestCounter implements RequestCounter {
  private readonly logger: ILogger
  private readonly monthlyQuota: number
  private usage: Map<string, { requests: number; resetAt: Date; lastUpdated: Date }>

  constructor(logger: ILogger, monthlyQuota: number = 500) {
    this.logger = logger.child('alibaba-counter')
    this.monthlyQuota = monthlyQuota
    this.usage = new Map()
  }

  recordRequest(provider: string, model: string, _tokens?: { input: number; output: number }): void {
    const key = `${provider}::${model}`
    const now = new Date()
    let record = this.usage.get(key)

    if (!record || now >= record.resetAt) {
      record = {
        requests: 0,
        resetAt: this.getNextMonthStart(now),
        lastUpdated: now,
      }
      this.usage.set(key, record)
    }

    record.requests++
    record.lastUpdated = now
  }

  getUsage(provider: string, model: string): UsageSnapshot {
    const key = `${provider}::${model}`
    const record = this.usage.get(key)
    const now = new Date()

    if (!record || now >= record.resetAt) {
      return {
        provider,
        model,
        billingModel: BillingModel.ALIBABA_CODING,
        usage: {
          requests: 0,
          tokens: 0,
          inputTokens: 0,
          outputTokens: 0,
          resetAt: this.getNextMonthStart(now),
          lastUpdated: now,
        },
        limit: this.monthlyQuota,
        percentUsed: 0,
      }
    }

    return {
      provider,
      model,
      billingModel: BillingModel.ALIBABA_CODING,
      usage: {
        requests: record.requests,
        tokens: record.requests,
        inputTokens: 0,
        outputTokens: 0,
        resetAt: record.resetAt,
        lastUpdated: record.lastUpdated,
      },
      limit: this.monthlyQuota,
      percentUsed: (record.requests / this.monthlyQuota) * 100,
    }
  }

  reset(provider: string, model: string): void {
    const key = `${provider}::${model}`
    this.usage.delete(key)
  }

  wouldExceedBudget(provider: string, model: string, _estimatedTokens?: { input: number; output: number }): boolean {
    const snapshot = this.getUsage(provider, model)
    return snapshot.percentUsed >= 100
  }

  private getNextMonthStart(from: Date): Date {
    const next = new Date(from)
    next.setMonth(next.getMonth() + 1)
    next.setDate(1)
    next.setHours(0, 0, 0, 0)
    return next
  }
}

// Billing Model Classification

/**
 * Determine the billing model for a provider+model combination.
 * Uses CostClassifier internally but provides more granular classification.
 */
export function getBillingModel(
  provider: string,
  model: string,
  costClassifier?: CostClassifier,
): BillingModel {
  const classifier = costClassifier || new CostClassifier()
  const category = classifier.classify(`${provider}/${model}`)

  // Local models
  if (category === 'local') {
    return BillingModel.LOCAL
  }

  // Check provider-specific billing models
  const providerLower = provider.toLowerCase()
  const modelLower = model.toLowerCase()

  // GitHub Copilot
  if (providerLower.includes('github-copilot') || providerLower.includes('github')) {
    return BillingModel.GITHUB_COPILOT
  }

  // Alibaba Coding
  if (providerLower.includes('alibaba') || providerLower.includes('dashscope')) {
    return BillingModel.ALIBABA_CODING
  }

  // Token-based for everything else (OpenAI, Anthropic, etc.)
  return BillingModel.TOKEN_BASED
}

/**
 * Factory function to get the appropriate request counter for a billing model.
 */
export function getRequestCounter(
  billingModel: BillingModel,
  logger: ILogger,
  costClassifier?: CostClassifier,
): RequestCounter {
  switch (billingModel) {
    case BillingModel.GITHUB_COPILOT:
      return new CopilotRequestCounter(logger)
    case BillingModel.ALIBABA_CODING:
      return new AlibabaRequestCounter(logger)
    case BillingModel.TOKEN_BASED:
      return new TokenRequestCounter(logger, costClassifier)
    case BillingModel.LOCAL:
      // Local models don't need tracking
      return new TokenRequestCounter(logger, costClassifier)
    default:
      throw new Error(`Unknown billing model: ${billingModel}`)
  }
}

/**
 * Get cost tier for a model based on CostClassifier and model characteristics.
 */
export function getCostTier(provider: string, model: string, costClassifier?: CostClassifier): 'free' | 'low' | 'medium' | 'high' {
  const classifier = costClassifier || new CostClassifier()
  const category = classifier.classify(`${provider}/${model}`)

  // Free models
  if (category === 'free' || category === 'local') {
    return 'free'
  }

  const modelLower = model.toLowerCase()

  // Small/fast models = low cost
  if (modelLower.includes('mini') || modelLower.includes('nano') || modelLower.includes('fast')) {
    return 'low'
  }

  // Large reasoning models = high cost
  if (modelLower.includes('max') || modelLower.includes('pro') || modelLower.includes('o1') || modelLower.includes('o3')) {
    return 'high'
  }

  // Default to medium
  return 'medium'
}
