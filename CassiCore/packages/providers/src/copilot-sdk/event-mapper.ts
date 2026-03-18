/**
 * SDK Event Mapper — maps Copilot SDK SessionEvent types to CassiCore event bus events.
 *
 * Handles streaming (message_delta → turn:token), tool events,
 * usage tracking, and error propagation.
 */
import type { SessionEvent } from '@github/copilot-sdk'

import type { IEventBus } from '../../../types/interfaces.js'

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
}

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
 */
export function mapSdkEvent(
  event: SessionEvent,
  state: SdkTurnState,
  bus: IEventBus,
  onStreamCallback?: (text: string) => void,
): boolean {
  switch (event.type) {
    // ── Streaming text ──────────────────────────────────────────────────
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

    // ── Final message (non-streaming or after all deltas) ───────────────
    case 'assistant.message': {
      // If text wasn't accumulated via deltas, use the final content
      if (!state.text && event.data.content) {
        state.text = event.data.content
      }
      return false
    }

    // ── Reasoning/thinking ──────────────────────────────────────────────
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

    // ── Tool execution start ────────────────────────────────────────────
    case 'tool.execution_start': {
      // CassiCore event already emitted by tool-bridge handler
      // This is informational for tracking
      return false
    }

    // ── Tool execution complete ─────────────────────────────────────────
    case 'tool.execution_complete': {
      const data = event.data
      state.toolOutputs.push({
        tool_name: 'sdk-tool',
        tool_call_id: data.toolCallId,
        output: data.result?.content ?? '',
        is_error: !data.success,
        timestamp: new Date(),
      })
      return false
    }

    // ── Usage / billing info ────────────────────────────────────────────
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

    // ── Turn lifecycle ──────────────────────────────────────────────────
    case 'assistant.turn_start': {
      return false
    }

    case 'assistant.turn_end': {
      return false
    }

    // ── Session idle — signals turn completion ──────────────────────────
    case 'session.idle': {
      return true // Turn complete
    }

    // ── Errors ──────────────────────────────────────────────────────────
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

    // ── Context management events (informational) ───────────────────────
    case 'session.truncation':
    case 'session.compaction_start':
    case 'session.compaction_complete':
    case 'session.usage_info': {
      // Log but don't act — SDK handles context management internally
      return false
    }

    default:
      // Unknown event type — ignore
      return false
  }
}
