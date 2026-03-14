/**
 * Consolidated Cassandra Event Stream Tools (Phase 2)
 *
 * Merges cassandra_get_state + cassandra_get_history into unified query interface.
 * Eliminates cassandra_subscribe and cassandra_invalidate_cache (documented alternatives).
 *
 * Preserves all caching behavior (StateCache with TTLs) from original implementation.
 */

import type { EventBus } from '../../event-bus.js'
import type { ToolDefinition, ToolHandler } from '../types.js'

// ============================================================================
// Constants
// ============================================================================

const STATE_CACHE_TTL_MS = 1000  // 1 second state cache
const MAX_EVENTS_RETURN = 1000   // Max events to return in one call

// ============================================================================
// State Cache with Incremental Updates (preserved from original)
// ============================================================================

interface CachedState {
  snapshot: any
  eventCount: number
  lastEventTimestamp: number
  computedAt: number
}

class StateCache {
  private cache = new Map<string, CachedState>()
  private ttlMs: number

  constructor(ttlMs: number = STATE_CACHE_TTL_MS) {
    this.ttlMs = ttlMs
  }

  get(sessionId: string, currentEventCount: number): CachedState | undefined {
    const cached = this.cache.get(sessionId)
    if (!cached) return undefined

    if (Date.now() - cached.computedAt > this.ttlMs) {
      this.cache.delete(sessionId)
      return undefined
    }

    if (cached.eventCount !== currentEventCount) {
      return undefined
    }

    return cached
  }

  set(sessionId: string, state: CachedState): void {
    this.cache.set(sessionId, state)
  }

  invalidate(sessionId?: string): void {
    if (sessionId) {
      this.cache.delete(sessionId)
    } else {
      this.cache.clear()
    }
  }

  stats(): { size: number; sessions: string[] } {
    return {
      size: this.cache.size,
      sessions: Array.from(this.cache.keys()).slice(0, 10)
    }
  }
}

const globalStateCache = new StateCache()

// ============================================================================
// Optimized State Builder (preserved from original)
// ============================================================================

interface StateBuilder {
  snapshot: any
  activeToolCalls: Map<string, { toolCallId: string; toolName: string; startTime: number }>
}

function createStateBuilder(): StateBuilder {
  return {
    snapshot: {
      connected: true,
      lastEventTimestamp: 0,
      turnIndex: 0,
      isStreaming: false,
      messageCount: 0,
      activeTools: [],
      activeToolCalls: [],
      totalTokensUsed: 0,
    },
    activeToolCalls: new Map(),
  }
}

function processEventBatch(builder: StateBuilder, events: any[]): void {
  for (const event of events) {
    const snapshot = builder.snapshot
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
        builder.activeToolCalls.set(event.toolCallId, {
          toolCallId: event.toolCallId,
          toolName: event.toolName,
          startTime: event.timestamp,
        })
        break
      case 'tool_execution_end':
        builder.activeToolCalls.delete(event.toolCallId)
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

  builder.snapshot.activeToolCalls = Array.from(builder.activeToolCalls.values())
}

function buildStateSnapshotOptimized(
  sessionId: string,
  events: any[],
  useCache: boolean = true
): any {
  if (useCache) {
    const cached = globalStateCache.get(sessionId, events.length)
    if (cached) {
      return cached.snapshot
    }
  }

  const builder = createStateBuilder()
  processEventBatch(builder, events)

  const snapshot = {
    sessionId,
    ...builder.snapshot,
  }

  if (useCache) {
    globalStateCache.set(sessionId, {
      snapshot,
      eventCount: events.length,
      lastEventTimestamp: snapshot.lastEventTimestamp,
      computedAt: Date.now(),
    })
  }

  return snapshot
}

// ============================================================================
// Efficient Event Filtering (preserved from original)
// ============================================================================

function* filterEventsLazy(
  events: any[],
  options: {
    since?: number
    eventTypes?: string[]
    limit?: number
  }
): Generator<any> {
  const { since, eventTypes, limit = MAX_EVENTS_RETURN } = options
  let count = 0

  for (let i = events.length - 1; i >= 0 && count < limit; i--) {
    const event = events[i]

    if (since !== undefined && event.timestamp < since) {
      continue
    }

    if (eventTypes && eventTypes.length > 0 && !eventTypes.includes(event.type)) {
      continue
    }

    yield event
    count++
  }
}

function filterEventsEfficient(
  events: any[],
  options: {
    since?: number
    eventTypes?: string[]
    limit?: number
  }
): { events: any[]; total: number; truncated: boolean } {
  const limit = Math.min(options.limit || 100, MAX_EVENTS_RETURN)
  const result: any[] = []

  for (const event of filterEventsLazy(events, { ...options, limit })) {
    result.push(event)
  }

  result.reverse()

  return {
    events: result,
    total: events.length,
    truncated: events.length > limit,
  }
}

// ============================================================================
// Consolidated Tool Definition
// ============================================================================

export const cassandraQueryEventsDef: ToolDefinition = {
  name: 'cassandra_query_events',
  description:
    'Query session event stream with unified interface. Use mode parameter to choose output:\n' +
    '- state: Get current session state snapshot (cached, optimized)\n' +
    '- history: Get event history with efficient filtering\n\n' +
    'Replaces cassandra_get_state and cassandra_get_history. ' +
    'For streaming, use HTTP endpoints directly (documented).',
  parameters: {
    type: 'object',
    properties: {
      sessionId: { type: 'string', description: 'Session ID to query' },
      mode: {
        type: 'string',
        description: 'Query mode',
        enum: ['state', 'history'],
        default: 'state',
      },
      // Options for 'state' mode
      noCache: { type: 'boolean', description: 'Bypass cache (for state mode)', default: false },
      // Options for 'history' mode
      since: { type: 'number', description: 'Timestamp to get events since (for history mode)' },
      limit: { type: 'number', description: 'Maximum events to return (for history mode, max 1000)', default: 100 },
      eventTypes: { type: 'array', items: { type: 'string' }, description: 'Filter by event types (for history mode)' },
      // Common
      compact: { type: 'boolean', description: 'Return compact JSON', default: false },
    },
    required: ['sessionId'],
  },
  timeoutMs: 5_000,
}

// ============================================================================
// Consolidated Handler
// ============================================================================

export function makeCassandraQueryEventsHandler(
  eventBus: EventBus
): ToolHandler {
  return async (input, ctx) => {
    const sessionId = input['sessionId'] as string
    const mode = (input['mode'] as string) ?? 'state'
    const compact = (input['compact'] as boolean) ?? false

    const startTime = Date.now()
    const events = eventBus.getAllEvents(sessionId)
    
    if (events.length === 0) {
      return JSON.stringify({ sessionId, error: 'No events found for session' })
    }

    let result: any

    if (mode === 'state') {
      const noCache = (input['noCache'] as boolean) ?? false
      const snapshot = buildStateSnapshotOptimized(sessionId, events, !noCache)
      result = snapshot

      ctx.logger.debug?.('[cassandra_query_events.state]', {
        sessionId,
        events: events.length,
        cached: !noCache && globalStateCache.get(sessionId, events.length) !== undefined,
        duration: `${Date.now() - startTime}ms`,
      })
    } else if (mode === 'history') {
      const since = input['since'] as number | undefined
      const limit = (input['limit'] as number) ?? 100
      const eventTypes = input['eventTypes'] as string[] | undefined

      const { events: filteredEvents, total, truncated } = filterEventsEfficient(events, {
        since,
        eventTypes,
        limit,
      })

      result = {
        sessionId,
        events: filteredEvents,
        total,
        truncated,
        returned: filteredEvents.length,
      }

      ctx.logger.debug?.('[cassandra_query_events.history]', {
        sessionId,
        total,
        returned: filteredEvents.length,
        filtered: !!eventTypes,
        duration: `${Date.now() - startTime}ms`,
      })
    } else {
      return JSON.stringify({ error: `Unknown mode "${mode}". Use "state" or "history".` })
    }

    return JSON.stringify(result, null, compact ? undefined : 2)
  }
}

// ============================================================================
// Registration Function
// ============================================================================

export function registerCassandraEventTools(
  registry: any,
  eventBus: EventBus,
  _getSessionId: () => string | undefined
): void {
  registry.register(cassandraQueryEventsDef, makeCassandraQueryEventsHandler(eventBus))
}

// Export cache for inspection
export { globalStateCache as stateCache }
