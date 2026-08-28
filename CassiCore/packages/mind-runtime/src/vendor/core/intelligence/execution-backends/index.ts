/**
 * Execution Backends — Factory and barrel exports.
 *
 * Usage:
 *   const backend = createExecutionBackend('cassicore', logger, { sessionPipeline })
 *   const backend = createExecutionBackend('opencode', logger, { openCodeConfig })
 */

import { CassiCoreExecutionBackend } from './cassicore-backend.js'
import { OpenCodeExecutionBackend } from './opencode-backend.js'
import { CachedValue } from '@cassicore/utils'

import type {
  IExecutionBackend,
  ExecutionBackendType,
  OpenCodeBackendConfig,
} from '@cassicore/foundation'
import type { ILogger } from '@cassicore/foundation'
// REMOVED: TurnPipeline import deleted — only SessionPipeline is supported

interface SessionPipelineLike {
  processTurn(
    sessionId: string,
    content: string,
    options?: {
      channelId?: string
      senderId?: string
      signal?: AbortSignal
      model?: string
    },
  ): Promise<{ response: string; sessionId: string; model?: string; tokensUsed?: number; durationMs?: number }>
}


export { CassiCoreExecutionBackend } from './cassicore-backend.js'
export { OpenCodeExecutionBackend } from './opencode-backend.js'

export interface BackendFactoryOpts {
  // REMOVED: pipeline deleted — only sessionPipeline is supported
  sessionPipeline?: SessionPipelineLike
  /** Config for 'opencode' backend */
  openCodeConfig?: OpenCodeBackendConfig
}

/**
 * Create an execution backend by type.
 *
 * - 'cassicore': uses SessionPipeline (requires opts.sessionPipeline)
 * - 'opencode': uses OpenCode HTTP API
 * - 'auto': tries OpenCode first, falls back to CassiCore if unavailable
 */
export function createExecutionBackend(
  type: ExecutionBackendType,
  logger: ILogger,
  opts: BackendFactoryOpts,
): IExecutionBackend {
  switch (type) {
    case 'cassicore':
      if (!opts.sessionPipeline) {
        throw new Error('CassiCore execution backend requires a SessionPipeline')
      }
      return new CassiCoreExecutionBackend(logger, opts.sessionPipeline)

    case 'opencode':
      return new OpenCodeExecutionBackend(logger, opts.openCodeConfig)

    case 'auto':
      // For 'auto', we create an AutoBackend that tries OpenCode first
      return new AutoExecutionBackend(logger, opts)

    default:
      throw new Error(`Unknown execution backend type: ${type}`)
  }
}


class AutoExecutionBackend implements IExecutionBackend {
  readonly name = 'auto'
  private logger: ILogger
  private openCodeBackend: OpenCodeExecutionBackend
  private cassiCoreBackend: CassiCoreExecutionBackend | null
  private cachedBackend = new CachedValue<IExecutionBackend>({ ttlMs: 60_000 })

  constructor(logger: ILogger, opts: BackendFactoryOpts) {
    this.logger = logger.child?.('exec-backend:auto') ?? logger
    this.openCodeBackend = new OpenCodeExecutionBackend(logger, opts.openCodeConfig)
    this.cassiCoreBackend = opts.sessionPipeline
      ? new CassiCoreExecutionBackend(logger, opts.sessionPipeline)
      : null
  }

  async execute(inbound: import('@cassicore/foundation').InboundMessage): Promise<import('@cassicore/foundation').TurnResult> {
    const backend = await this.resolveBackend()
    try {
      return await backend.execute(inbound)
    } catch (err) {
      // Invalidate cache on connection errors
      const errorMsg = err instanceof Error ? err.message : String(err)
      if (
        errorMsg.includes('ECONNREFUSED') ||
        errorMsg.includes('fetch failed') ||
        errorMsg.includes('ETIMEDOUT') ||
        errorMsg.includes('ENOTFOUND') ||
        errorMsg.includes('socket')
      ) {
        this.cachedBackend.invalidate()
        this.logger.warn('AutoBackend: invalidated cache due to connection error', { error: errorMsg })
      }
      throw err
    }
  }

  async initAgentSession(agentId: string, sessionId: string, opts: import('@cassicore/foundation').AgentSessionOpts): Promise<void> {
    const backend = await this.resolveBackend()
    return backend.initAgentSession(agentId, sessionId, opts)
  }

  async destroyAgentSession(agentId: string): Promise<void> {
    // Use .value to bypass TTL for cleanup operations
    const backend = this.cachedBackend.value
    if (backend) {
      return backend.destroyAgentSession(agentId)
    }
  }

  async isAvailable(): Promise<boolean> {
    // Always check fresh — do NOT use cached backend
    return this.openCodeBackend.isAvailable()
      .then(ok => ok || (this.cassiCoreBackend?.isAvailable() ?? Promise.resolve(false)))
  }

  async updateContext?(
    agentId: string,
    context: { systemPrompt?: string; recentMemories?: string[]; files?: string[] },
  ): Promise<void> {
    // Use .value to bypass TTL check for context updates
    this.cachedBackend.value?.updateContext?.(agentId, context)
  }

  private async resolveBackend(): Promise<IExecutionBackend> {
    const cached = this.cachedBackend.get()
    if (cached) return cached

    // Try OpenCode first
    const openCodeAvailable = await this.openCodeBackend.isAvailable()
    if (openCodeAvailable) {
      this.cachedBackend.set(this.openCodeBackend)
      this.logger.info('AutoBackend: resolved to OpenCode')
      return this.openCodeBackend
    }

    // Fall back to CassiCore
    if (this.cassiCoreBackend) {
      this.cachedBackend.set(this.cassiCoreBackend)
      this.logger.info('AutoBackend: fell back to CassiCore (OpenCode unavailable)')
      return this.cassiCoreBackend
    }

    throw new Error('AutoBackend: no execution backend available (OpenCode unreachable, no SessionPipeline)')
  }
}
