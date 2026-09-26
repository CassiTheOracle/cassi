/**
 * CassiCoreExecutionBackend — Wraps SessionPipeline.processTurn().
 *
 * Execution backend for autonomous agent iterations through CassiCore's
 * SessionPipeline with intelligence modules, provider routing, and tool execution.
 */

import type { IExecutionBackend, AgentSessionOpts } from '@cassicore/foundation'
import type { ILogger } from '@cassicore/foundation'
import type { InboundMessage, TurnResult } from '@cassicore/foundation'
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

export class CassiCoreExecutionBackend implements IExecutionBackend {
  readonly name = 'cassicore'
  private logger: ILogger
  private sessionPipeline: SessionPipelineLike

  constructor(logger: ILogger, sessionPipeline: SessionPipelineLike) {
    this.logger = logger.child?.('exec-backend:cassicore') ?? logger
    this.sessionPipeline = sessionPipeline
  }

  async execute(inbound: InboundMessage): Promise<TurnResult> {
    const result = await this.sessionPipeline.processTurn(inbound.sessionId, inbound.content, {
      channelId: inbound.channelId,
      senderId: inbound.senderId,
    })
    return {
      response: result.response,
      tokensUsed: typeof result.tokensUsed === 'number' ? result.tokensUsed : 0,
      model: result.model ?? 'unknown',
      durationMs: result.durationMs ?? 0,
    }
  }

  async initAgentSession(_agentId: string, _sessionId: string, _opts: AgentSessionOpts): Promise<void> {
    // No-op: CassiCore sessions are managed by SessionManager, already created
    // before the autonomous loop starts.
  }

  async destroyAgentSession(_agentId: string): Promise<void> {
    // No-op: session cleanup is handled by MultiAgentCoordinator
  }

  async isAvailable(): Promise<boolean> {
    return !!this.sessionPipeline
  }
}
