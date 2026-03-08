import { GitHubCopilotProvider } from './github-copilot.js'
import { BaseProvider } from './base.js'

import type { Message, CompletionOpts, CompletionChunk, ImageAttachment } from '../../types/runtime.js'

/**
 * GitHub Copilot account descriptor
 */
export interface GitHubCopilotAccount {
  profileId: string
  oauthToken: string
}

export interface LoadBalancerConfig {
  accounts: GitHubCopilotAccount[]
  strategy?: 'round-robin' | 'least-loaded' | 'weighted'
  weights?: number[]
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

export class GitHubCopilotLoadBalancer extends BaseProvider {
  readonly id = 'github-copilot-lb'
  readonly models = ['gemini-3-flash-preview', 'gemini-3-pro-preview', 'claude-sonnet-4.6', 'gpt-5-mini']

  private accounts: GitHubCopilotAccount[]
  private providers: GitHubCopilotProvider[]
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
    this.cooldownMs = config.cooldownMs ?? 60000
    this.maxRetries = config.maxRetries ?? 2

    this.providers = config.accounts.map(acc => new GitHubCopilotProvider(acc.oauthToken, acc.profileId))

    this.stats = config.accounts.map(acc => ({
      profileId: acc.profileId,
      requests: 0,
      errors: 0,
      lastUsed: 0,
    }))
  }

  private isOnCooldown(index: number): boolean {
    const stat = this.stats[index]
    if (!stat.cooldownUntil) return false
    return Date.now() < stat.cooldownUntil
  }

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

  private getNextRoundRobin(lastIndex?: number): number {
    const start = lastIndex !== undefined ? lastIndex + 1 : this.currentIndex
    const attempts: number[] = []
    for (let i = 0; i < this.accounts.length; i++) {
      const idx = (start + i) % this.accounts.length
      if (!this.isOnCooldown(idx)) attempts.push(idx)
    }
    if (attempts.length === 0) return this.getLeastRecentIndex()
    this.currentIndex = attempts[0]
    return this.currentIndex
  }

  private getNextLeastLoaded(now: number): number {
    let bestIdx = 0
    let bestScore = Infinity
    for (let i = 0; i < this.stats.length; i++) {
      if (this.isOnCooldown(i)) continue
      const stat = this.stats[i]
      const score = stat.requests + (stat.errors * 10)
      if (score < bestScore) {
        bestScore = score
        bestIdx = i
      }
    }
    this.currentIndex = bestIdx
    return bestIdx
  }

  private getNextWeighted(): number {
    const totalWeight = this.weights.reduce((a, b) => a + b, 0)
    let random = Math.random() * totalWeight
    for (let i = 0; i < this.weights.length; i++) {
      if (this.isOnCooldown(i)) continue
      random -= this.weights[i]
      if (random <= 0) { this.currentIndex = i; return i }
    }
    return this.getNextRoundRobin()
  }

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

  private recordSuccess(index: number) {
    const stat = this.stats[index]
    stat.requests++
    stat.lastUsed = Date.now()
    stat.rateLimited = false
  }

  private recordError(index: number, errMsg: string) {
    const stat = this.stats[index]
    stat.errors++
    stat.lastUsed = Date.now()
    stat.lastError = Date.now()
    if (errMsg.includes('429') || errMsg.toLowerCase().includes('rate limit')) {
      stat.rateLimited = true
      stat.cooldownUntil = Date.now() + this.cooldownMs
    }
  }

  private getProvider(index: number): GitHubCopilotProvider {
    return this.providers[index]
  }

  async *complete(
    messages: Message[],
    opts: CompletionOpts,
    attachments?: ImageAttachment[],
    signal?: AbortSignal,
  ): AsyncIterable<CompletionChunk> {
    let attempts = 0
    let lastIndex: number | undefined
    let lastErrMsg: string | undefined

    while (attempts < this.maxRetries) {
      const index = this.getNextIndex(lastIndex)
      const provider = this.getProvider(index)

      // Create abort controller to cancel provider if we failover
      const controller = new AbortController()
      if (signal) {
        if (signal.aborted) controller.abort()
        else signal.addEventListener('abort', () => controller.abort(), { once: true })
      }

      let failed = false
      try {
        for await (const chunk of provider.complete(messages, opts, attachments, controller.signal)) {
          if (chunk.type === 'error') {
            const errMsg = chunk.error || 'unknown error'
            // Decide action based on error text
            if (errMsg.includes('cancelled') || errMsg.includes('aborted')) {
              yield { type: 'error', error: 'cancelled' }
              return
            }

            // Record error and decide whether to failover
            this.recordError(index, errMsg)
            lastErrMsg = errMsg

            // Rate limit -> set cooldown (recordError did) and move to next
            if (errMsg.includes('429') || errMsg.toLowerCase().includes('rate limit')) {
              failed = true
              break
            }

            // 502 or network -> try failover
            if (errMsg.includes('502') || errMsg.toLowerCase().includes('network error')) {
              failed = true
              break
            }

            // Other errors: surface and stop
            yield { type: 'error', error: errMsg }
            return
          }

          // Forward normal chunks
          yield chunk
        }

        if (!failed) {
          // Completed successfully
          this.recordSuccess(index)
          return
        }
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : String(err)
        this.recordError(index, errMsg)
        lastErrMsg = errMsg
        // If aborted externally
        if (errMsg.includes('Abort') || errMsg.includes('cancelled')) {
          yield { type: 'error', error: 'cancelled' }
          return
        }
        failed = true
      } finally {
        try { controller.abort() } catch {}
      }

      // If we reach here, this attempt failed and we should try next account
      attempts++
      lastIndex = index
    }

    yield { type: 'error', error: `All GitHub Copilot accounts failed after ${attempts} attempts: ${lastErrMsg || 'unknown'}` }
  }

  async countTokens(messages: Message[]): Promise<number> {
    const provider = this.getProvider(this.currentIndex)
    return provider.countTokens(messages)
  }

  async ping(signal?: AbortSignal): Promise<boolean> {
    const results = await Promise.all(this.providers.map(p => p.ping(signal)))
    return results.some(r => r)
  }

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

  resetStats() {
    this.stats = this.accounts.map(acc => ({ profileId: acc.profileId, requests: 0, errors: 0, lastUsed: 0 }))
    this.currentIndex = 0
  }

  setCooldown(profileId: string, durationMs: number) {
    const stat = this.stats.find(s => s.profileId === profileId)
    if (stat) stat.cooldownUntil = Date.now() + durationMs
  }

  getActiveCount(): number {
    const now = Date.now()
    return this.stats.filter(s => !s.cooldownUntil || now >= s.cooldownUntil).length
  }
}

/**
 * Create load balancer from account profiles
 */
export function createGitHubCopilotLoadBalancer(
  accounts: GitHubCopilotAccount[],
  options?: Partial<Omit<LoadBalancerConfig, 'accounts'>>,
): GitHubCopilotLoadBalancer {
  return new GitHubCopilotLoadBalancer({
    accounts,
    strategy: 'round-robin',
    cooldownMs: 60000,
    maxRetries: 2,
    ...options,
  })
}
