/**
 * SDK Event Mapper — maps Copilot SDK SessionEvent types to CassiCore event bus events.
 *
 * Handles streaming (message_delta → turn:token), tool events,
 * usage tracking, and error propagation.
 */
import type { SessionEvent } from '@github/copilot-sdk'

import type { IEventBus } from '@cassicore/foundation'

/** Context health snapshot captured from SDK session events. */
export interface SdkContextHealth {
  /** Maximum token count for the model's context window */
  tokenLimit: number
  /** Current number of tokens in the context window */
  currentTokens: number
  /** Fill level as a fraction (0.0-1.0) */
  fillLevel: number
  /** Current number of messages in the conversation */
  messagesLength: number
  /** Whether background compaction is currently in progress */
  isCompacting: boolean
  /** Number of compaction events during this turn */
  compactionsDuringTurn: number
  /** Number of truncation events during this turn */
  truncationsDuringTurn: number
  /** Tokens recovered via compaction during this turn */
  tokensRecoveredByCompaction: number
  /** Tokens removed via truncation during this turn */
  tokensRemovedByTruncation: number
  /** LLM-generated summary from compaction (if available) */
  compactionSummary?: string
}

/** Accumulated state for a single SDK turn. */
export interface SdkTurnState {
  sessionId: string
  text: string
  thinkingText: string
  toolCalls: Array<{ name: string; durationMs: number }>
  toolOutputs: Array<{
    tool_name: string
    tool_call_id: string
    output: string
    is_error: boolean
    timestamp: Date
  }>
  tokensUsed: number
  model: string
  startedAt: number
  /** Context health data captured from SDK session events during the turn */
  contextHealth?: SdkContextHealth
  /** Internal: tracks in-flight tool calls for duration measurement */
  _pendingToolCalls?: Map<string, { name: string; startedAt: number }>
}

/**
 * @dep callers: executeSdkTurn (core/providers/copilot-sdk/provider.ts)
 * @dep calls: now
 * @dep flows: ExecuteSdkTurn → Now (2/3)
 * @dep module: Providers
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */

export function createTurnState(sessionId: string): SdkTurnState {
  return {
    sessionId,
    text: '',
    thinkingText: '',
    toolCalls: [],
    toolOutputs: [],
    tokensUsed: 0,
    model: '',
    startedAt: Date.now(),
  }
}

/** Emit a worker:message event (the CassiCore convention for turn-level events). */
/**
 * @dep callers: mapSdkEvent (core/providers/copilot-sdk/event-mapper.ts)
 * @dep calls: emit
 * @dep flows: ExecuteSdkTurn → EmitWorkerMessage (3/3)
 * @dep module: Tests
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */

function emitWorkerMessage(bus: IEventBus, sessionId: string, payload: Record<string, unknown>): void {
  bus.emit({
    type: 'worker:message',
    pluginId: `session:${sessionId}`,
    payload,
  })
}

/**
 * Map a Copilot SDK SessionEvent to CassiCore event bus events.
 * Updates the accumulated turn state as events arrive.
 *
 * @returns true if this event signals the turn is complete (session.idle)
 * @dep callers: executeSdkTurn (core/providers/copilot-sdk/provider.ts)
 * @dep calls: emit, now, emitWorkerMessage
 * @dep flows: ExecuteSdkTurn → EmitWorkerMessage (2/3)
 * @dep module: Tests
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */
export function mapSdkEvent(
  event: SessionEvent,
  state: SdkTurnState,
  bus: IEventBus,
  onStreamCallback?: (text: string) => void,
): boolean {
  switch (event.type) {
    case 'assistant.message_delta': {
      const delta = event.data.deltaContent
      state.text += delta
      if (onStreamCallback) onStreamCallback(delta)
      emitWorkerMessage(bus, state.sessionId, {
        type: 'turn:token',
        sessionId: state.sessionId,
        token: delta,
      })
      return false
    }

    case 'assistant.message': {
      // If text wasn't accumulated via deltas, use the final content
      if (!state.text && event.data.content) {
        state.text = event.data.content
      }
      return false
    }

    case 'assistant.reasoning_delta': {
      state.thinkingText += event.data.deltaContent
      emitWorkerMessage(bus, state.sessionId, {
        type: 'turn:thinking',
        sessionId: state.sessionId,
        token: event.data.deltaContent,
      })
      return false
    }

    case 'assistant.reasoning': {
      if (!state.thinkingText) {
        state.thinkingText = event.data.content
      }
      return false
    }

    case 'tool.execution_start': {
      const data = event.data as { toolCallId?: string; toolName?: string }
      if (data.toolCallId) {
        state._pendingToolCalls = state._pendingToolCalls ?? new Map()
        state._pendingToolCalls.set(data.toolCallId, {
          name: data.toolName ?? 'unknown',
          startedAt: Date.now(),
        })
      }
      return false
    }

    case 'tool.execution_complete': {
      const data = event.data
      const pending = state._pendingToolCalls?.get(data.toolCallId)
      const toolName = pending?.name ?? 'sdk-tool'
      const durationMs = pending ? Date.now() - pending.startedAt : 0
      state._pendingToolCalls?.delete(data.toolCallId)

      state.toolCalls.push({ name: toolName, durationMs })
      state.toolOutputs.push({
        tool_name: toolName,
        tool_call_id: data.toolCallId,
        output: data.result?.content ?? '',
        is_error: !data.success,
        timestamp: new Date(),
      })
      return false
    }

    case 'assistant.usage': {
      const usage = event.data
      state.tokensUsed += (usage.inputTokens ?? 0) + (usage.outputTokens ?? 0)
      if (usage.model) state.model = usage.model

      bus.emit({
        type: 'provider:request_end' as never,
        providerId: 'copilot-sdk',
        requestId: `sdk_${Date.now()}`,
        sessionId: state.sessionId,
        source: 'copilot-sdk',
        model: usage.model ?? state.model,
        tokensUsed: {
          input: usage.inputTokens ?? 0,
          output: usage.outputTokens ?? 0,
          thinking: 0,
        },
        durationMs: usage.duration ?? 0,
        timestamp: new Date(),
      } as never)
      return false
    }

    case 'assistant.turn_start': {
      return false
    }

    case 'assistant.turn_end': {
      return false
    }

    case 'session.idle': {
      return true // Turn complete
    }

    case 'session.error': {
      bus.emit({
        type: 'provider:request_error' as never,
        providerId: 'copilot-sdk',
        requestId: `sdk_${Date.now()}`,
        sessionId: state.sessionId,
        source: 'copilot-sdk',
        model: state.model,
        error: event.data.message,
        consecutiveErrors: 0,
        durationMs: Date.now() - state.startedAt,
        timestamp: new Date(),
      } as never)
      return false
    }

    case 'session.usage_info': {
      const d = (event as any).data
      const tokenLimit = d?.tokenLimit ?? 0
      const currentTokens = d?.currentTokens ?? 0
      if (!state.contextHealth) {
        state.contextHealth = {
          tokenLimit,
          currentTokens,
          fillLevel: tokenLimit > 0 ? currentTokens / tokenLimit : 0,
          messagesLength: d?.messagesLength ?? 0,
          isCompacting: false,
          compactionsDuringTurn: 0,
          truncationsDuringTurn: 0,
          tokensRecoveredByCompaction: 0,
          tokensRemovedByTruncation: 0,
        }
      } else {
        state.contextHealth.tokenLimit = tokenLimit
        state.contextHealth.currentTokens = currentTokens
        state.contextHealth.fillLevel = tokenLimit > 0 ? currentTokens / tokenLimit : 0
        state.contextHealth.messagesLength = d?.messagesLength ?? 0
      }
      return false
    }

    case 'session.compaction_start': {
      if (state.contextHealth) {
        state.contextHealth.isCompacting = true
      }
      return false
    }

    case 'session.compaction_complete': {
      const d = (event as any).data
      if (state.contextHealth) {
        state.contextHealth.isCompacting = false
        state.contextHealth.compactionsDuringTurn++
        const tokensRecovered = (d?.preCompactionTokens ?? 0) - (d?.postCompactionTokens ?? 0)
        if (tokensRecovered > 0) {
          state.contextHealth.tokensRecoveredByCompaction += tokensRecovered
        }
        if (d?.postCompactionTokens != null) {
          state.contextHealth.currentTokens = d.postCompactionTokens
          if (state.contextHealth.tokenLimit > 0) {
            state.contextHealth.fillLevel = d.postCompactionTokens / state.contextHealth.tokenLimit
          }
        }
        if (d?.summaryContent) {
          state.contextHealth.compactionSummary = d.summaryContent
        }
      }
      if (!d?.success) {
        bus.emit({
          type: 'provider:request_error' as never,
          providerId: 'copilot-sdk',
          requestId: `sdk_compaction_${Date.now()}`,
          sessionId: state.sessionId,
          source: 'copilot-sdk',
          model: state.model,
          error: `Compaction failed: ${d?.error ?? 'unknown'}`,
          consecutiveErrors: 0,
          durationMs: 0,
          timestamp: new Date(),
        } as never)
      }
      return false
    }

    case 'session.truncation': {
      const d = (event as any).data
      if (state.contextHealth) {
        state.contextHealth.truncationsDuringTurn++
        state.contextHealth.tokensRemovedByTruncation += d?.tokensRemovedDuringTruncation ?? 0
        if (d?.postTruncationTokensInMessages != null) {
          state.contextHealth.currentTokens = d.postTruncationTokensInMessages
          if (state.contextHealth.tokenLimit > 0) {
            state.contextHealth.fillLevel = d.postTruncationTokensInMessages / state.contextHealth.tokenLimit
          }
        }
        state.contextHealth.messagesLength = d?.postTruncationMessagesLength ?? state.contextHealth.messagesLength
      }
      return false
    }

    default:
      // Unknown event type — ignore
      return false
  }
}
