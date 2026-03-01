/**
 * StreamIngestor — Real-time token stream processing
 * 
 * Captures and buffers tokens, thinking blocks, and tool interactions
 * from the main agent's stream. Maintains per-session sliding window
 * buffers with full preservation of reasoning chains.
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type {
  TokenBuffer,
  TokenMetadata,
  ToolCallRecord,
  BufferStats,
  StreamIngestor as IStreamIngestor,
  StreamConfig,
} from './types.js'

// ============================================================================
// TokenBuffer Implementation
// ============================================================================

export class TokenBufferImpl implements TokenBuffer {
  sessionId: string
  tokens: string[] = []
  thinking: string[] = []
  toolCalls: ToolCallRecord[] = []
  lastActivity: number
  createdAt: number

  private maxTokens: number
  private windowTokens: number

  constructor(sessionId: string, maxTokens: number, windowTokens: number) {
    this.sessionId = sessionId
    this.maxTokens = maxTokens
    this.windowTokens = windowTokens
    this.createdAt = Date.now()
    this.lastActivity = this.createdAt
  }

  append(token: string): void {
    this.tokens.push(token)
    this.lastActivity = Date.now()
    
    // Trim if we exceed max tokens
    if (this.tokens.length > this.maxTokens) {
      this.trimToMaxTokens(this.maxTokens)
    }
  }

  appendThinking(thinking: string): void {
    this.thinking.push(thinking)
    this.lastActivity = Date.now()
  }

  addToolCall(tool: string, input: unknown): string {
    const id = `tc_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
    const record: ToolCallRecord = {
      id,
      tool,
      input,
      timestamp: Date.now(),
    }
    this.toolCalls.push(record)
    this.lastActivity = Date.now()
    return id
  }

  addToolResult(callId: string, result: unknown): void {
    const call = this.toolCalls.find(tc => tc.id === callId)
    if (call) {
      call.result = result
      call.durationMs = Date.now() - call.timestamp
      this.lastActivity = Date.now()
    }
  }

  trimToMaxTokens(maxTokens: number): void {
    if (this.tokens.length <= maxTokens) return
    
    // Keep the most recent tokens, archive older ones
    const toRemove = this.tokens.length - maxTokens
    this.tokens = this.tokens.slice(toRemove)
  }

  getRecentTokens(count: number): string[] {
    return this.tokens.slice(-count)
  }

  getText(): string {
    return this.tokens.join('')
  }

  getThinking(): string {
    return this.thinking.join('')
  }

  getRecentThinking(maxChars?: number): string {
    const full = this.getThinking()
    if (maxChars && full.length > maxChars) {
      // Return the end of the thinking (most recent)
      return '...' + full.slice(-maxChars)
    }
    return full
  }

  getToolHistory(): ToolCallRecord[] {
    return [...this.toolCalls]
  }

  getStats(): BufferStats {
    const activeCalls = this.toolCalls.filter(tc => tc.result === undefined).length
    return {
      totalTokens: this.tokens.length,
      totalThinkingChars: this.thinking.reduce((sum, t) => sum + t.length, 0),
      totalToolCalls: this.toolCalls.length,
      activeToolCalls: activeCalls,
      sessionDurationMs: Date.now() - this.createdAt,
    }
  }
}

// ============================================================================
// StreamIngestor Implementation
// ============================================================================

export interface StreamIngestorOptions {
  config: StreamConfig
  logger: ILogger
  eventBus?: IEventBus
}

export class StreamIngestorImpl implements IStreamIngestor {
  private buffers = new Map<string, TokenBufferImpl>()
  private config: StreamConfig
  private logger: ILogger
  private eventBus?: IEventBus
  private tokenCounter = new Map<string, number>() // For pattern check intervals

  constructor(options: StreamIngestorOptions) {
    this.config = options.config
    this.logger = options.logger.child?.('stream-ingestor') ?? options.logger
    this.eventBus = options.eventBus
  }

  onToken(sessionId: string, token: string, metadata?: TokenMetadata): void {
    const buffer = this.getOrCreateBuffer(sessionId)
    buffer.append(token)

    // Track for pattern check interval
    const count = (this.tokenCounter.get(sessionId) || 0) + 1
    this.tokenCounter.set(sessionId, count)

    // Emit buffer updated event (throttled to every N tokens)
    if (count % this.config.patternCheckInterval === 0) {
      this.emitBufferUpdated(sessionId, buffer)
    }

    // Emit token event for real-time consumers
    this.emitToken(sessionId, token, buffer)
  }

  onThinking(sessionId: string, thinking: string): void {
    const buffer = this.getOrCreateBuffer(sessionId)
    buffer.appendThinking(thinking)

    this.emitThinking(sessionId, thinking)
    this.emitBufferUpdated(sessionId, buffer)
  }

  onToolCall(sessionId: string, tool: string, input: unknown): void {
    const buffer = this.getOrCreateBuffer(sessionId)
    const callId = buffer.addToolCall(tool, input)

    this.logger.debug('Tool call captured', { sessionId: sessionId.slice(-8), tool, callId })
    this.emitTool(sessionId, tool, 'call')
    this.emitBufferUpdated(sessionId, buffer)
  }

  onToolResult(sessionId: string, tool: string, result: unknown, callId?: string): void {
    const buffer = this.buffers.get(sessionId)
    if (!buffer) {
      this.logger.warn('Tool result for unknown session', { sessionId: sessionId.slice(-8), tool })
      return
    }

    // If we have a callId, update that specific call
    if (callId) {
      buffer.addToolResult(callId, result)
    } else {
      // Otherwise, find the most recent pending call for this tool
      const pendingCall = buffer.toolCalls
        .slice()
        .reverse()
        .find(tc => tc.tool === tool && tc.result === undefined)
      
      if (pendingCall) {
        buffer.addToolResult(pendingCall.id, result)
      } else {
        this.logger.warn('No pending tool call found for result', { sessionId: sessionId.slice(-8), tool })
      }
    }

    this.emitTool(sessionId, tool, 'result')
    this.emitBufferUpdated(sessionId, buffer)
  }

  getBuffer(sessionId: string): TokenBuffer | undefined {
    return this.buffers.get(sessionId)
  }

  cleanupSession(sessionId: string): void {
    const buffer = this.buffers.get(sessionId)
    if (buffer) {
      this.logger.debug('Cleaning up session buffer', { sessionId: sessionId.slice(-8) })
      
      // Emit final stats before cleanup
      this.emitBufferUpdated(sessionId, buffer)
      
      this.buffers.delete(sessionId)
      this.tokenCounter.delete(sessionId)
    }
  }

  getActiveSessions(): string[] {
    return Array.from(this.buffers.keys())
  }

  // ============================================================================
  // Private Helpers
  // ============================================================================

  private getOrCreateBuffer(sessionId: string): TokenBufferImpl {
    let buffer = this.buffers.get(sessionId)
    if (!buffer) {
      buffer = new TokenBufferImpl(
        sessionId,
        this.config.bufferMaxTokens,
        this.config.slidingWindowTokens
      )
      this.buffers.set(sessionId, buffer)
      this.logger.debug('Created new token buffer', { sessionId: sessionId.slice(-8) })
    }
    return buffer
  }

  private emitToken(sessionId: string, token: string, buffer: TokenBuffer): void {
    if (!this.eventBus) return
    
    try {
      this.eventBus.emit?.({
        type: 'subconscious:token',
        sessionId,
        token,
        bufferSize: buffer.tokens.length,
        timestamp: Date.now(),
      } as any)
    } catch (err) {
      this.logger.debug('Failed to emit token event', { error: String(err) })
    }
  }

  private emitThinking(sessionId: string, thinking: string): void {
    if (!this.eventBus) return
    
    try {
      this.eventBus.emit?.({
        type: 'subconscious:thinking',
        sessionId,
        thinking,
        timestamp: Date.now(),
      } as any)
    } catch (err) {
      this.logger.debug('Failed to emit thinking event', { error: String(err) })
    }
  }

  private emitTool(sessionId: string, tool: string, direction: 'call' | 'result'): void {
    if (!this.eventBus) return
    
    try {
      this.eventBus.emit?.({
        type: 'subconscious:tool',
        sessionId,
        tool,
        direction,
        timestamp: Date.now(),
      } as any)
    } catch (err) {
      this.logger.debug('Failed to emit tool event', { error: String(err) })
    }
  }

  private emitBufferUpdated(sessionId: string, buffer: TokenBuffer): void {
    if (!this.eventBus) return
    
    try {
      this.eventBus.emit?.({
        type: 'subconscious:buffer:updated',
        sessionId,
        stats: buffer.getStats(),
        timestamp: Date.now(),
      } as any)
    } catch (err) {
      this.logger.debug('Failed to emit buffer updated event', { error: String(err) })
    }
  }
}

// ============================================================================
// Factory
// ============================================================================

export function createStreamIngestor(
  config: StreamConfig,
  logger: ILogger,
  eventBus?: IEventBus
): StreamIngestorImpl {
  return new StreamIngestorImpl({ config, logger, eventBus })
}
