/**
 * Qwen Load Balancer - Round-Robin Multi-Account Management
 * 
 * Distributes requests across multiple Qwen OAuth accounts to:
 * - Avoid rate limits
 * - Increase throughput
 * - Provide failover on errors
 */

import { QwenProvider, type QwenOAuthCredentials } from './vendor/ai/providers/cassicore/index.js'

import { BaseProvider } from './base.js'

import type { Message, CompletionOpts, CompletionChunk, ImageAttachment } from '@cassicore/foundation'

export interface QwenAccount {
  profileId: string
  credentials: QwenOAuthCredentials
  baseUrl?: string
}

export interface LoadBalancerConfig {
  accounts: QwenAccount[]
  strategy: 'round-robin' | 'least-loaded' | 'weighted'
  weights?: number[]  // For weighted strategy
  cooldownMs?: number
  maxRetries?: number
}

interface AccountStats {
  profileId: string
  requests: number
  errors: number
  lastUsed: number
  lastError?: number
  cooldownUntil?: number
  rateLimited?: boolean
}

/**
 * Round-robin load balancer for Qwen accounts
 */
export class QwenLoadBalancer extends BaseProvider {
  readonly id = 'qwen-lb'
  readonly models = ['coder-model', 'vision-model']

  private accounts: QwenAccount[]
  private providers: QwenProvider[]
  private stats: AccountStats[]
  private currentIndex = 0
  private cooldownMs: number
  private maxRetries: number
  private strategy: 'round-robin' | 'least-loaded' | 'weighted'
  private weights: number[]

  constructor(config: LoadBalancerConfig) {
    super()
    this.accounts = config.accounts
    this.strategy = config.strategy || 'round-robin'
    this.weights = config.weights || config.accounts.map(() => 1)
    this.cooldownMs = config.cooldownMs ?? 60000  // 1 minute default
    this.maxRetries = config.maxRetries ?? 2

    // Create provider instance per account
    this.providers = config.accounts.map(acc => 
      new QwenProvider(acc.credentials.access, acc.baseUrl, acc.credentials)
    )

    // Initialize stats
    this.stats = config.accounts.map(acc => ({
      profileId: acc.profileId,
      requests: 0,
      errors: 0,
      lastUsed: 0,
    }))
  }

  /**
   * Get next account index based on strategy
   */
  private getNextIndex(lastIndex?: number): number {
    const now = Date.now()

    switch (this.strategy) {
      case 'round-robin':
        return this.getNextRoundRobin(lastIndex)
      
      case 'least-loaded':
        return this.getNextLeastLoaded(now)
      
      case 'weighted':
        return this.getNextWeighted()
      
      default:
        return this.getNextRoundRobin(lastIndex)
    }
  }

  /**
   * Simple round-robin: cycle through accounts sequentially
   */
  private getNextRoundRobin(lastIndex?: number): number {
    const start = lastIndex !== undefined ? lastIndex + 1 : this.currentIndex
    const attempts: number[] = []
    
    // Collect all available indices
    for (let i = 0; i < this.accounts.length; i++) {
      const idx = (start + i) % this.accounts.length
      if (!this.isOnCooldown(idx)) {
        attempts.push(idx)
      }
    }

    if (attempts.length === 0) {
      // All on cooldown, use least recent
      return this.getLeastRecentIndex()
    }

    this.currentIndex = attempts[0]
    return this.currentIndex
  }

  /**
   * Least-loaded: pick account with fewest recent requests
   */
  private getNextLeastLoaded(now: number): number {
    const windowMs = 60000  // 1 minute window
    const cutoff = now - windowMs

    // Find account with lowest load score
    let bestIdx = 0
    let bestScore = Infinity

    for (let i = 0; i < this.stats.length; i++) {
      if (this.isOnCooldown(i)) continue

      const stat = this.stats[i]
      // Score = recent requests + error penalty
      const score = stat.requests + (stat.errors * 10)

      if (score < bestScore) {
        bestScore = score
        bestIdx = i
      }
    }

    this.currentIndex = bestIdx
    return bestIdx
  }

  /**
   * Weighted: distribute based on weights
   */
  private getNextWeighted(): number {
    const totalWeight = this.weights.reduce((a, b) => a + b, 0)
    let random = Math.random() * totalWeight
    
    for (let i = 0; i < this.weights.length; i++) {
      if (this.isOnCooldown(i)) continue
      random -= this.weights[i]
      if (random <= 0) {
        this.currentIndex = i
        return i
      }
    }

    // Fallback to round-robin
    return this.getNextRoundRobin()
  }

  /**
   * Check if account is on cooldown
   */
  private isOnCooldown(index: number): boolean {
    const stat = this.stats[index]
    if (!stat.cooldownUntil) return false
    return Date.now() < stat.cooldownUntil
  }

  /**
   * Get least recently used index
   */
  private getLeastRecentIndex(): number {
    let minIdx = 0
    let minTime = Infinity

    for (let i = 0; i < this.stats.length; i++) {
      if (this.stats[i].lastUsed < minTime) {
        minTime = this.stats[i].lastUsed
        minIdx = i
      }
    }

    return minIdx
  }

  /**
   * Record request success
   */
  private recordSuccess(index: number) {
    const stat = this.stats[index]
    stat.requests++
    stat.lastUsed = Date.now()
    stat.rateLimited = false
  }

  /**
   * Record request failure
   */
  private recordError(index: number, error: Error) {
    const stat = this.stats[index]
    stat.errors++
    stat.lastUsed = Date.now()
    stat.lastError = Date.now()

    // Check if rate limit error
    if (error.message.includes('429') || error.message.includes('rate limit')) {
      stat.rateLimited = true
      stat.cooldownUntil = Date.now() + this.cooldownMs
    }
  }

  /**
   * Get provider for specific index
   */
  private getProvider(index: number): QwenProvider {
    return this.providers[index]
  }

  async *complete(
    messages: Message[],
    opts: CompletionOpts,
    attachments?: ImageAttachment[],
    signal?: AbortSignal,
  ): AsyncIterable<CompletionChunk> {
    let lastError: Error | undefined
    let attempts = 0
    let lastIndex: number | undefined

    while (attempts < this.maxRetries) {
      try {
        // Get next account
        const index = this.getNextIndex(lastIndex)
        const provider = this.getProvider(index)

        // Stream completion
        for await (const chunk of provider.complete(messages, opts, attachments, signal)) {
          yield chunk
        }

        // Success
        this.recordSuccess(index)
        return
      } catch (err) {
        const error = err instanceof Error ? err : new Error(String(err))
        lastError = error
        attempts++

        // Record error and try next account
        if (lastIndex !== undefined) {
          this.recordError(lastIndex, error)
        }

        // Don't retry on certain errors
        if (error.message.includes('cancelled') || error.message.includes('aborted')) {
          yield { type: 'error', error: 'cancelled' }
          return
        }

        // Check if token expired - trigger refresh for next attempt
        if (error.message.includes('token') || error.message.includes('auth') || error.message.includes('401')) {
          const index = this.currentIndex
          try {
            const account = this.accounts[index]
            if (account) {
              const newCreds = await QwenProvider.refreshToken(account.credentials)
              account.credentials = newCreds
              // Update provider with new token
              this.providers[index] = new QwenProvider(newCreds.access, account.baseUrl, newCreds)
            }
          } catch (refreshErr) {
            // Refresh failed, continue to next account
          }
        }

        lastIndex = this.currentIndex
      }
    }

    // All retries exhausted
    yield { type: 'error', error: `All Qwen accounts failed after ${attempts} attempts: ${lastError?.message}` }
  }

  async countTokens(messages: Message[]): Promise<number> {
    // Use current provider for token counting
    const provider = this.getProvider(this.currentIndex)
    return provider.countTokens(messages)
  }

  async ping(signal?: AbortSignal): Promise<boolean> {
    // Ping all accounts, return true if any healthy
    const results = await Promise.all(
      this.providers.map(p => p.ping(signal))
    )
    return results.some(r => r)
  }

  /**
   * Get current stats for monitoring
   */
  getStats(): Array<{
    profileId: string
    requests: number
    errors: number
    lastUsed: number
    onCooldown: boolean
    rateLimited: boolean
  }> {
    const now = Date.now()
    return this.stats.map(stat => ({
      profileId: stat.profileId,
      requests: stat.requests,
      errors: stat.errors,
      lastUsed: stat.lastUsed,
      onCooldown: stat.cooldownUntil ? now < stat.cooldownUntil : false,
      rateLimited: stat.rateLimited || false,
    }))
  }

  /**
   * Reset stats (for testing)
   */
  resetStats() {
    this.stats = this.accounts.map(acc => ({
      profileId: acc.profileId,
      requests: 0,
      errors: 0,
      lastUsed: 0,
    }))
    this.currentIndex = 0
  }

  /**
   * Manually set cooldown for an account
   */
  setCooldown(profileId: string, durationMs: number) {
    const stat = this.stats.find(s => s.profileId === profileId)
    if (stat) {
      stat.cooldownUntil = Date.now() + durationMs
    }
  }

  /**
   * Get active account count
   */
  getActiveCount(): number {
    const now = Date.now()
    return this.stats.filter(s => !s.cooldownUntil || now >= s.cooldownUntil).length
  }
}

/**
 * Create load balancer from auth profiles
 */
export function createQwenLoadBalancer(
  profiles: Array<{ profileId: string; credentials: QwenOAuthCredentials; baseUrl?: string }>,
  options?: Partial<LoadBalancerConfig>,
): QwenLoadBalancer {
  return new QwenLoadBalancer({
    accounts: profiles,
    strategy: 'round-robin',
    cooldownMs: 60000,
    maxRetries: 2,
    ...options,
  })
}
