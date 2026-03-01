/**
 * Context Window Debugging Tools
 *
 * Tools for Cassandra to inspect and tail context windows being sent to models.
 */

import type { ToolDefinition, ToolHandler } from '../types.js'
import type { ContextWindowDebugger } from '../../events/context-window-debug.js'

// Tool definitions
export const cassandraGetContextWindowDef: ToolDefinition = {
  name: 'cassandra_get_context_window',
  description: 'Get the latest context window snapshot - shows exactly what was sent to the model',
  parameters: {
    type: 'object',
    properties: {
      sessionId: { type: 'string', description: 'Session ID to get context window for' },
      includeFullContent: { type: 'boolean', description: 'Include full message content (may be large)', default: true },
    },
    required: ['sessionId'],
  },
  timeoutMs: 5_000,
}

export const cassandraGetContextHistoryDef: ToolDefinition = {
  name: 'cassandra_get_context_history',
  description: 'Get history of context window snapshots to see how context evolved',
  parameters: {
    type: 'object',
    properties: {
      sessionId: { type: 'string', description: 'Session ID' },
      since: { type: 'number', description: 'Timestamp to get snapshots since' },
      limit: { type: 'number', description: 'Maximum snapshots to return', default: 10 },
    },
    required: ['sessionId'],
  },
  timeoutMs: 5_000,
}

export const cassandraGetContextStatsDef: ToolDefinition = {
  name: 'cassandra_get_context_stats',
  description: 'Get statistics about context window usage for a session',
  parameters: {
    type: 'object',
    properties: {
      sessionId: { type: 'string', description: 'Session ID' },
    },
    required: ['sessionId'],
  },
  timeoutMs: 5_000,
}

export const cassandraTailContextWindowDef: ToolDefinition = {
  name: 'cassandra_tail_context_window',
  description: 'Get SSE URL to tail context window updates in real-time (like `tail -f`)',
  parameters: {
    type: 'object',
    properties: {
      sessionId: { type: 'string', description: 'Session ID to tail' },
      baseUrl: { type: 'string', description: 'Daemon base URL', default: 'http://localhost:7433' },
    },
    required: ['sessionId'],
  },
  timeoutMs: 5_000,
}

// Handler factories
export function makeCassandraGetContextWindowHandler(
  getDebugger: () => ContextWindowDebugger | null
): ToolHandler {
  return async (input, _ctx) => {
    const sessionId = input['sessionId'] as string
    const includeFullContent = input['includeFullContent'] as boolean ?? true

    const ctxDebugger = getDebugger()
    if (!ctxDebugger) {
      return 'Error: Context window debugging is not enabled on the daemon. Set debug.contextWindow.enabled: true in config.'
    }

    const snapshot = ctxDebugger.getLatestSnapshot(sessionId)
    if (!snapshot) {
      return `No context window snapshot found for session ${sessionId}. Has any turn been processed yet?`
    }

    // Format the output
    const result = includeFullContent ? snapshot : {
      ...snapshot,
      messages: snapshot.messages.map(m => ({
        role: m.role,
        contentLength: m.content?.length || 0,
        preview: m.content?.slice(0, 200) + (m.content?.length && m.content.length > 200 ? '...' : ''),
      })),
    }

    return JSON.stringify(result, null, 2)
  }
}

export function makeCassandraGetContextHistoryHandler(
  getDebugger: () => ContextWindowDebugger | null
): ToolHandler {
  return async (input, _ctx) => {
    const sessionId = input['sessionId'] as string
    const since = input['since'] as number | undefined
    const limit = (input['limit'] as number) ?? 10

    const ctxDebugger = getDebugger()
    if (!ctxDebugger) {
      return 'Error: Context window debugging is not enabled on the daemon.'
    }

    const snapshots = since
      ? ctxDebugger.getSnapshotsSince(sessionId, since)
      : ctxDebugger.getSnapshots(sessionId)

    if (snapshots.length === 0) {
      return `No context window snapshots found for session ${sessionId}`
    }

    // Return summaries of snapshots
    const summaries = snapshots.slice(-limit).map(s => ({
      timestamp: s.timestamp,
      turnIndex: s.turnIndex,
      model: s.model,
      messageCount: s.messageCount,
      estimatedTokens: s.estimatedTokens,
      percentUsed: s.percentUsed,
      totalChars: s.totalChars,
      systemPromptLength: s.systemPromptLength,
      historyMessageCount: s.historyMessageCount,
      userMessageLength: s.userMessageLength,
      contentHash: s.contentHash,
    }))

    return JSON.stringify({
      sessionId,
      snapshots: summaries,
      totalSnapshots: snapshots.length,
    }, null, 2)
  }
}

export function makeCassandraGetContextStatsHandler(
  getDebugger: () => ContextWindowDebugger | null
): ToolHandler {
  return async (input, _ctx) => {
    const sessionId = input['sessionId'] as string

    const ctxDebugger = getDebugger()
    if (!ctxDebugger) {
      return 'Error: Context window debugging is not enabled on the daemon.'
    }

    const stats = ctxDebugger.getStats(sessionId)

    return JSON.stringify({
      sessionId,
      stats,
    }, null, 2)
  }
}

export function makeCassandraTailContextWindowHandler(
  getDebugger: () => ContextWindowDebugger | null
): ToolHandler {
  return async (input, _ctx) => {
    const sessionId = input['sessionId'] as string
    const baseUrl = (input['baseUrl'] as string) ?? 'http://localhost:7433'

    const ctxDebugger = getDebugger()
    if (!ctxDebugger) {
      return 'Error: Context window debugging is not enabled on the daemon.'
    }

    const latest = ctxDebugger.getLatestSnapshot(sessionId)

    const result = {
      sessionId,
      streamUrl: `${baseUrl}/debug/context-window/stream?sessionId=${encodeURIComponent(sessionId)}`,
      currentSnapshot: latest ? {
        timestamp: latest.timestamp,
        turnIndex: latest.turnIndex,
        model: latest.model,
        messageCount: latest.messageCount,
        estimatedTokens: latest.estimatedTokens,
      } : null,
      usage: `curl -N "${baseUrl}/debug/context-window/stream?sessionId=${sessionId}"`,
    }

    return JSON.stringify(result, null, 2)
  }
}

// Registration function
export function registerContextWindowTools(
  registry: any,
  getDebugger: () => ContextWindowDebugger | null
): void {
  registry.register(
    cassandraGetContextWindowDef,
    makeCassandraGetContextWindowHandler(getDebugger)
  )
  registry.register(
    cassandraGetContextHistoryDef,
    makeCassandraGetContextHistoryHandler(getDebugger)
  )
  registry.register(
    cassandraGetContextStatsDef,
    makeCassandraGetContextStatsHandler(getDebugger)
  )
  registry.register(
    cassandraTailContextWindowDef,
    makeCassandraTailContextWindowHandler(getDebugger)
  )
}
