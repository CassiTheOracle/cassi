/**
 * ModelHandle - Lightweight Model Reference with Lifecycle Management
 */

import type { ModelHandle, ModelCompletionOpts, ModelCapabilities, BudgetScope } from './types.js'
import type { IProvider, TurnResult, Message, CompletionChunk } from '../../types/runtime.js'
import type { ILogger } from '../../types/interfaces.js'
import { BudgetManager } from './budget-manager.js'
import { FallbackManager } from './fallback-manager.js'

/**
 * Internal state for ModelHandle
 */
interface ModelHandleState {
  released: boolean
  totalTokens: number
  requestCount: number
}

/**
 * ModelHandle implementation
 */
export class ModelHandleImpl implements ModelHandle {
  readonly provider: string
  readonly model: string
  readonly capabilities: ModelCapabilities
  readonly budgetScope?: BudgetScope

  private readonly providerInstance: IProvider
  private readonly budgetManager: BudgetManager
  private readonly fallbackManager: FallbackManager
  private readonly logger: ILogger
  readonly slotName: string
  private readonly onRelease: (handle: ModelHandleImpl) => void
  private state: ModelHandleState

  constructor(
    provider: string,
    model: string,
    capabilities: ModelCapabilities,
    providerInstance: IProvider,
    budgetManager: BudgetManager,
    budgetScopeId: string | undefined,
    logger: ILogger,
    slotName: string,
    onRelease: (handle: ModelHandleImpl) => void,
    fallbackManager: FallbackManager,
  ) {
    this.provider = provider
    this.model = model
    this.capabilities = capabilities
    this.providerInstance = providerInstance
    this.budgetManager = budgetManager
    this.fallbackManager = fallbackManager
    this.logger = logger.child(`ModelHandle:${slotName}`)
    this.slotName = slotName
    this.onRelease = onRelease
    this.state = {
      released: false,
      totalTokens: 0,
      requestCount: 0,
    }

    if (budgetScopeId) {
      const scope = this.budgetManager.getScope(budgetScopeId)
      if (scope) {
        this.budgetScope = scope
      }
    }

    this.logger.debug('ModelHandle created', {
      provider,
      model,
      capabilities: {
        contextWindow: capabilities.contextWindow,
        supportsTools: capabilities.supportsTools,
        costTier: capabilities.costTier,
      },
    })
  }

  /**
   * Execute a completion request with the model.
   */
  async complete(messages: Message[], opts: ModelCompletionOpts): Promise<TurnResult> {
    if (this.state.released) {
      const error = new Error('ModelHandle has been released')
      this.logger.warn('complete() called on released handle', { model: this.model })
      throw error
    }

    if (this.budgetScope) {
      const status = this.budgetManager.checkBudget(this.budgetScope.id)

      if (!status.allowed) {
        this.logger.warn('Budget exceeded — continuing execution (tracking only)', {
          scopeId: this.budgetScope.id,
          reason: status.reason,
        })
      }
    }

    this.state.requestCount++
    const startTime = Date.now()

    try {
      let content = ''
      let totalTokens = 0

      for await (const chunk of this.providerInstance.complete(
        this.normalizeMessages(messages),
        {
          ...opts,
          model: this.model,
        },
      )) {
        if (chunk.type === 'token' || chunk.type === 'thinking') {
          content += chunk.text ?? ''
        }

        if (chunk.tokensUsed) {
          totalTokens += chunk.tokensUsed
        }
      }

      const durationMs = Date.now() - startTime

      const result: TurnResult = {
        response: content,
        tokensUsed: totalTokens,
        model: this.model,
        durationMs,
      }

      await this.trackUsage(result)

      this.logger.debug('Completion successful', {
        model: this.model,
        tokens: result.tokensUsed,
        durationMs,
      })

      return result
    } catch (error) {
      this.logger.error('Completion failed', {
        model: this.model,
        error: error instanceof Error ? error.message : String(error),
      })

      // Auto-report failure to fallback manager
      const failureReason = this.determineFailureReason(error)
      this.fallbackManager.reportFailure(
        this.slotName,
        this.provider,
        this.model,
        failureReason,
      )

      throw error
    }
  }

  /**
   * Stream a completion request, yielding chunks for agentic tool loops.
   * Provides the same budget checks and failure reporting as complete(),
   * but exposes the raw chunk stream instead of aggregating.
   */
  async *stream(messages: Message[], opts: ModelCompletionOpts): AsyncIterable<CompletionChunk> {
    if (this.state.released) {
      throw new Error('ModelHandle has been released')
    }

    if (this.budgetScope) {
      const status = this.budgetManager.checkBudget(this.budgetScope.id)
      if (!status.allowed) {
        this.logger.warn('Budget exceeded — continuing execution (tracking only)', {
          scopeId: this.budgetScope.id,
          reason: status.reason,
        })
      }
    }

    this.state.requestCount++
    let totalTokens = 0
    const startTime = Date.now()

    try {
      for await (const chunk of this.providerInstance.complete(
        this.normalizeMessages(messages),
        {
          ...opts,
          model: this.model,
        },
      )) {
        if (chunk.tokensUsed) {
          totalTokens += chunk.tokensUsed
        }
        yield chunk
      }

      // Track usage on successful completion
      const durationMs = Date.now() - startTime
      this.state.totalTokens += totalTokens
      if (this.budgetScope) {
        await this.budgetManager.trackUsage(this.budgetScope.id, {
          inputTokens: 0,
          outputTokens: totalTokens,
          requests: 1,
        })
      }
      this.logger.debug('Stream completed', { model: this.model, tokens: totalTokens, durationMs })
    } catch (error) {
      this.logger.error('Stream failed', {
        model: this.model,
        error: error instanceof Error ? error.message : String(error),
      })
      const failureReason = this.determineFailureReason(error)
      this.fallbackManager.reportFailure(this.slotName, this.provider, this.model, failureReason)
      throw error
    }
  }

  /**
   * Determine the failure reason from an error.
   */
  private determineFailureReason(error: unknown): 'rate_limit' | 'timeout' | 'model_unavailable' | 'budget_exceeded' | 'circuit_open' | 'error' {
    if (error instanceof Error) {
      const err = error as any
      const status = err.status || err.response?.status
      
      if (status === 429) return 'rate_limit'
      if (status === 408 || status === 504) return 'timeout'
      if (status === 503) return 'model_unavailable'
      if (status >= 500) return 'error'
      
      // Check error message for hints
      const message = err.message?.toLowerCase() || ''
      if (message.includes('rate limit')) return 'rate_limit'
      if (message.includes('timeout')) return 'timeout'
      if (message.includes('unavailable')) return 'model_unavailable'
      if (message.includes('budget')) return 'budget_exceeded'
      if (message.includes('circuit')) return 'circuit_open'
    }
    
    return 'error'
  }

  /**
   * Release the model back to the pool.
   */
  release(): void {
    if (this.state.released) {
      this.logger.debug('release() called on already released handle')
      return
    }

    this.state.released = true
    this.logger.info('ModelHandle released', {
      provider: this.provider,
      model: this.model,
      totalTokens: this.state.totalTokens,
      requestCount: this.state.requestCount,
    })

    this.onRelease(this)
  }

  /**
   * Symbol.dispose for automatic cleanup.
   */
  [Symbol.dispose](): void {
    if (!this.state.released) {
      this.logger.debug('Auto-releasing ModelHandle via Symbol.dispose')
      this.release()
    }
  }

  /**
   * Get current usage statistics.
   */
  getStats(): {
    totalTokens: number
    totalInputTokens: number
    totalOutputTokens: number
    requestCount: number
    released: boolean
  } {
    return {
      totalTokens: this.state.totalTokens,
      totalInputTokens: 0,
      totalOutputTokens: 0,
      requestCount: this.state.requestCount,
      released: this.state.released,
    }
  }

  /**
   * Normalize messages for the provider.
   */
  private normalizeMessages(messages: Message[]): Message[] {
    return messages
  }

  /**
   * Track token usage in the budget manager.
   */
  private async trackUsage(result: TurnResult): Promise<void> {
    if (!this.budgetScope) return

    this.state.totalTokens += result.tokensUsed

    await this.budgetManager.trackUsage(this.budgetScope.id, {
      inputTokens: 0,
      outputTokens: result.tokensUsed,
      requests: 1,
    })
  }
}
