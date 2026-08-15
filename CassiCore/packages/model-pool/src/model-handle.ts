/**
 * @cassicore/model-pool — retained ModelHandleImpl (CASSICORE-FOCUS §19 / §6 P4)
 *
 * The retained completion runtime. At P4 the provider/budget/fallback tie-ins
 * were stripped and `complete()`/`stream()` retarget the retained seam to a
 * `mind_complete`-shaped transport (injected; ohmypi owns providers + routing).
 *
 * `stream()` is a single-shot adaptation: the retained `mind_complete`
 * transport returns the full completion text, so the shim yields one `token`
 * chunk (the full text) then a `done` chunk. Token-level streaming and
 * `tool_use` chunks route through ohmypi task-agents (plan §2.3 option A) —
 * not through this raw-completion shim. Consumers that need agentic tool loops
 * should launch task agents; this handle is the raw-completion cast.
 */

import type { ModelHandle, ModelCompletionOpts, ModelCapabilities } from './types.js'
import type { TurnResult, Message, CompletionChunk } from '@cassicore/foundation'
import type { ILogger } from '@cassicore/foundation'
import type { MindCompleteTransport } from './mind-complete.js'

/** Internal state for the retained handle. */
interface ModelHandleState {
  released: boolean
  totalTokens: number
  requestCount: number
}

/** Constructor options for the retained, mind_complete-backed handle. */
export interface ModelHandleImplOpts {
  provider: string
  model: string
  capabilities: ModelCapabilities
  transport: MindCompleteTransport
  logger: ILogger
  slotName: string
  onRelease?: (handle: ModelHandleImpl) => void
}

/**
 * ModelHandle implementation — retained completion runtime over an injected
 * `mind_complete` transport.
 */
export class ModelHandleImpl implements ModelHandle {
  readonly provider: string
  readonly model: string
  readonly capabilities: ModelCapabilities

  private readonly transport: MindCompleteTransport
  private readonly logger: ILogger
  readonly slotName: string
  private readonly onRelease?: (handle: ModelHandleImpl) => void
  private state: ModelHandleState

  constructor(opts: ModelHandleImplOpts) {
    this.provider = opts.provider
    this.model = opts.model
    this.capabilities = opts.capabilities
    this.transport = opts.transport
    this.logger = opts.logger.child(`ModelHandle:${opts.slotName}`)
    this.slotName = opts.slotName
    this.onRelease = opts.onRelease
    this.state = {
      released: false,
      totalTokens: 0,
      requestCount: 0,
    }

    this.logger.debug('ModelHandle created (mind_complete-backed)', {
      provider: opts.provider,
      model: opts.model,
      slotName: opts.slotName,
    })
  }

  /**
   * Execute a completion request with the model — routed through the retained
   * `mind_complete` transport.
   */
  async complete(messages: Message[], opts: ModelCompletionOpts): Promise<TurnResult> {
    if (this.state.released) {
      const error = new Error('ModelHandle has been released')
      this.logger.warn('complete() called on released handle', { model: this.model })
      throw error
    }

    this.state.requestCount++
    const startTime = Date.now()

    try {
      const resolved = { id: `${this.provider}/${this.model}` }
      const { content, usage, model } = await this.transport(
        resolved,
        this.serializeMessages(messages),
        {
          effort: undefined,
          temperature: opts.temperature,
          model: this.model,
        },
      )

      const totalTokens = this.extractUsageTokens(usage)
      this.state.totalTokens += totalTokens
      const durationMs = Date.now() - startTime

      const result: TurnResult = {
        response: content,
        tokensUsed: totalTokens,
        model: model ?? this.model,
        durationMs,
      }

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
      throw error
    }
  }

  /**
   * Stream a completion request — single-shot `mind_complete` adaptation:
   * yields the full text as one `token` chunk followed by a `done` chunk.
   */
  async *stream(messages: Message[], opts: ModelCompletionOpts): AsyncIterable<CompletionChunk> {
    if (this.state.released) {
      throw new Error('ModelHandle has been released')
    }

    this.state.requestCount++
    const startTime = Date.now()
    let totalTokens = 0

    try {
      const resolved = { id: `${this.provider}/${this.model}` }
      const { content, usage, model } = await this.transport(
        resolved,
        this.serializeMessages(messages),
        {
          effort: undefined,
          temperature: opts.temperature,
          model: this.model,
        },
      )

      totalTokens = this.extractUsageTokens(usage)

      if (content) {
        yield {
          type: 'token',
          text: content,
          tokensUsed: totalTokens,
        }
      }

      this.state.totalTokens += totalTokens
      const durationMs = Date.now() - startTime
      this.logger.debug('Stream completed (single-shot)', {
        model: this.model,
        tokens: totalTokens,
        durationMs,
      })

      yield {
        type: 'done',
        tokensUsed: totalTokens,
        model: model ?? this.model,
      }
    } catch (error) {
      this.logger.error('Stream failed', {
        model: this.model,
        error: error instanceof Error ? error.message : String(error),
      })
      yield {
        type: 'error',
        error: error instanceof Error ? error.message : String(error),
      }
    }
  }

  /**
   * Release the model back to the pool (no-op bookkeeping; ohmypi owns the pool).
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

    this.onRelease?.(this)
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
   * Get current usage statistics (retained for compatibility).
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
      totalOutputTokens: this.state.totalTokens,
      requestCount: this.state.requestCount,
      released: this.state.released,
    }
  }

  /** Flatten foundation Messages (string | ContentBlock[]) to text for transport. */
  private serializeMessages(messages: Message[]): Array<{ role: string; content: string }> {
    return messages.map((m) => ({
      role: m.role,
      content:
        typeof m.content === 'string'
          ? m.content
          : Array.isArray(m.content)
            ? m.content
                .map((b) => (b && typeof b === 'object' && 'text' in b && typeof (b as any).text === 'string' ? (b as any).text : ''))
                .filter(Boolean)
                .join('\n')
            : String(m.content),
    }))
  }

  /** Extract a token count from the transport's usage payload when surfaced. */
  private extractUsageTokens(usage: unknown): number {
    if (!usage || typeof usage !== 'object') return 0
    const u = usage as Record<string, unknown>
    if (typeof u.totalTokens === 'number') return u.totalTokens
    if (typeof u.outputTokens === 'number') return u.outputTokens
    if (typeof u.total_tokens === 'number') return u.total_tokens
    return 0
  }
}
