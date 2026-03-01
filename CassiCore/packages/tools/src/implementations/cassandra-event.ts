/**
 * Cassandra Event Stream Tools
 *
 * Tools for Cassandra to query session state and events.
 */

import type { ToolDefinition, ToolHandler } from '../types.js'
import type { CassiCoreEventBus } from '../../events/event-bus.js'

// Tool definitions
export const cassandraGetStateDef: ToolDefinition = {
  name: 'cassandra_get_state',
  description: 'Get current session state snapshot from event stream',
  parameters: {
    type: 'object',
    properties: {
      sessionId: { type: 'string', description: 'Session ID to get state for' },
    },
    required: ['sessionId'],
  },
  timeoutMs: 5_000,
}

export const cassandraGetHistoryDef: ToolDefinition = {
  name: 'cassandra_get_history',
  description: 'Get event history for a session',
  parameters: {
    type: 'object',
    properties: {
      sessionId: { type: 'string', description: 'Session ID' },
      since: { type: 'number', description: 'Timestamp to get events since' },
      limit: { type: 'number', description: 'Maximum events to return', default: 100 },
      eventTypes: { type: 'array', items: { type: 'string' }, description: 'Filter by event types' },
    },
    required: ['sessionId'],
  },
  timeoutMs: 5_000,
}

export const cassandraSubscribeDef: ToolDefinition = {
  name: 'cassandra_subscribe',
  description: 'Subscribe to streaming events for a session (returns SSE URL)',
  parameters: {
    type: 'object',
    properties: {
      sessionId: { type: 'string', description: 'Session ID' },
      baseUrl: { type: 'string', description: 'Daemon base URL', default: 'http://localhost:7433' },
    },
    required: ['sessionId'],
  },
  timeoutMs: 5_000,
}

// Handler factories
export function makeCassandraGetStateHandler(
  eventBus: CassiCoreEventBus
): ToolHandler {
  return async (input, _ctx) => {
    const sessionId = input['sessionId'] as string

    const events = eventBus.getAllEvents(sessionId)
    const snapshot = buildStateSnapshot(sessionId, events)

    return JSON.stringify(snapshot, null, 2)
  }
}

export function makeCassandraGetHistoryHandler(
  eventBus: CassiCoreEventBus
): ToolHandler {
  return async (input, _ctx) => {
    const sessionId = input['sessionId'] as string
    const since = input['since'] as number | undefined
    const limit = (input['limit'] as number) ?? 100
    const eventTypes = input['eventTypes'] as string[] | undefined

    let events = since
      ? eventBus.getEventsSince(sessionId, since)
      : eventBus.getRecentEvents(sessionId, limit)

    if (eventTypes && eventTypes.length > 0) {
      events = events.filter((e: any) => eventTypes.includes(e.type))
    }

    return JSON.stringify({
      events: events.slice(0, limit),
      total: events.length,
      sessionId,
    }, null, 2)
  }
}

export function makeCassandraSubscribeHandler(
  eventBus: CassiCoreEventBus
): ToolHandler {
  return async (input, _ctx) => {
    const sessionId = input['sessionId'] as string
    const baseUrl = (input['baseUrl'] as string) ?? 'http://localhost:7433'

    return JSON.stringify({
      sseUrl: `${baseUrl}/events/stream?sessionId=${encodeURIComponent(sessionId)}`,
      historyUrl: `${baseUrl}/events/history?sessionId=${encodeURIComponent(sessionId)}`,
      stateUrl: `${baseUrl}/state?sessionId=${encodeURIComponent(sessionId)}`,
    }, null, 2)
  }
}

// Helper function
function buildStateSnapshot(sessionId: string, events: any[]): any {
  const snapshot: any = {
    sessionId,
    connected: true,
    lastEventTimestamp: 0,
    turnIndex: 0,
    isStreaming: false,
    messageCount: 0,
    activeTools: [],
    activeToolCalls: [],
    totalTokensUsed: 0,
  }

  const activeToolCalls = new Map<string, { toolCallId: string; toolName: string; startTime: number }>()

  for (const event of events) {
    snapshot.lastEventTimestamp = Math.max(snapshot.lastEventTimestamp, event.timestamp || 0)

    switch (event.type) {
      case 'session_start':
        snapshot.sessionStartTime = event.timestamp
        break
      case 'agent_start':
        snapshot.turnIndex = event.turnIndex || 0
        snapshot.model = event.model
        break
      case 'streaming_start':
        snapshot.isStreaming = true
        break
      case 'streaming_end':
        snapshot.isStreaming = false
        break
      case 'user_message':
      case 'assistant_message':
        snapshot.messageCount++
        break
      case 'assistant_message':
        snapshot.totalTokensUsed += (event.inputTokens || 0) + (event.outputTokens || 0)
        break
      case 'tool_execution_start':
        activeToolCalls.set(event.toolCallId, {
          toolCallId: event.toolCallId,
          toolName: event.toolName,
          startTime: event.timestamp,
        })
        break
      case 'tool_execution_end':
        activeToolCalls.delete(event.toolCallId)
        break
      case 'model_select':
        snapshot.model = event.model
        break
      case 'context_usage':
        snapshot.contextUsage = {
          tokens: event.tokens,
          contextWindow: event.contextWindow,
          percent: event.percent,
        }
        break
    }
  }

  snapshot.activeToolCalls = Array.from(activeToolCalls.values())
  return snapshot
}

// Registration function
export function registerCassandraEventTools(
  registry: any,
  eventBus: CassiCoreEventBus,
  _getSessionId: () => string | undefined
): void {
  registry.register(
    cassandraGetStateDef,
    makeCassandraGetStateHandler(eventBus)
  )
  registry.register(
    cassandraGetHistoryDef,
    makeCassandraGetHistoryHandler(eventBus)
  )
  registry.register(
    cassandraSubscribeDef,
    makeCassandraSubscribeHandler(eventBus)
  )
}
