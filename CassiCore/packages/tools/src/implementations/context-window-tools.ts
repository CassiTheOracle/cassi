/**
 * Optimized Context Window Debugging Tools
 *
 * Improvements:
 * - Lazy snapshot loading with field projection
 * - Summary caching to avoid recomputing
 * - Streaming for large context windows
 * - Efficient pagination
 */

import type { ContextWindowDebugger, ContextWindowSnapshot } from '../../events/context-window-debug.js'
import type { ToolDefinition, ToolHandler } from '../types.js'

// ============================================================================
// Constants
// ============================================================================

const SUMMARY_CACHE_TTL_MS = 2000  // 2 seconds
const MAX_SNAPSHOTS_DEFAULT = 50

// ============================================================================
// Summary Cache
// ============================================================================

interface SummaryCacheEntry {
  summaries: any[]
  snapshotCount: number
  lastSnapshotTimestamp: number
  computedAt: number
}

class SummaryCache {
  private cache = new Map<string, SummaryCacheEntry>()
  private ttlMs: number

  constructor(ttlMs: number = SUMMARY_CACHE_TTL_MS) {
    this.ttlMs = ttlMs
  }

  get(sessionId: string, currentSnapshotCount: number, lastTimestamp: number): SummaryCacheEntry | undefined {
    const cached = this.cache.get(sessionId)
    if (!cached) return undefined

    if (Date.now() - cached.computedAt > this.ttlMs) {
      this.cache.delete(sessionId)
      return undefined
    }

    if (cached.snapshotCount !== currentSnapshotCount ||
        cached.lastSnapshotTimestamp !== lastTimestamp) {
      return undefined
    }

    return cached
  }

  set(sessionId: string, entry: SummaryCacheEntry): void {
    this.cache.set(sessionId, entry)
  }

  invalidate(sessionId?: string): void {
    if (sessionId) {
      this.cache.delete(sessionId)
    } else {
      this.cache.clear()
    }
  }
}

const globalSummaryCache = new SummaryCache()

// ============================================================================
// Optimized Snapshot Processing
// ============================================================================

interface SnapshotSummary {
  timestamp: number
  turnIndex: number
  model: string
  messageCount: number
  estimatedTokens: number
  percentUsed: number
  totalChars: number
  systemPromptLength: number
  historyMessageCount: number
  userMessageLength: number
  contentHash: string
}

function createSnapshotSummary(snapshot: ContextWindowSnapshot): SnapshotSummary {
  return {
    timestamp: snapshot.timestamp,
    turnIndex: snapshot.turnIndex,
    model: snapshot.model,
    messageCount: snapshot.messageCount,
    estimatedTokens: snapshot.estimatedTokens,
    percentUsed: snapshot.percentUsed,
    totalChars: snapshot.totalChars,
    systemPromptLength: snapshot.systemPromptLength,
    historyMessageCount: snapshot.historyMessageCount,
    userMessageLength: snapshot.userMessageLength,
    contentHash: snapshot.contentHash,
  }
}

function* lazySnapshotSummaries(
  snapshots: ContextWindowSnapshot[],
  limit: number
): Generator<SnapshotSummary> {
  const start = Math.max(0, snapshots.length - limit)
  for (let i = start; i < snapshots.length; i++) {
    yield createSnapshotSummary(snapshots[i])
  }
}

// ============================================================================
// Field Projection for Messages
// ============================================================================

function projectSnapshot(
  snapshot: ContextWindowSnapshot,
  includeFullContent: boolean,
  maxContentLength: number = 10000
): any {
  if (includeFullContent) {
    // Still truncate extremely long content
    return {
      ...snapshot,
      messages: snapshot.messages.map(m => ({
        ...m,
        content: m.content?.length > maxContentLength
          ? `${m.content.slice(0, maxContentLength)  }\n... [truncated]`
          : m.content,
      })),
    }
  }

  // Return summary only
  return {
    type: snapshot.type,
    sessionId: snapshot.sessionId,
    timestamp: snapshot.timestamp,
    eventId: snapshot.eventId,
    turnIndex: snapshot.turnIndex,
    model: snapshot.model,
    messageCount: snapshot.messageCount,
    totalChars: snapshot.totalChars,
    estimatedTokens: snapshot.estimatedTokens,
    contextWindow: snapshot.contextWindow,
    percentUsed: snapshot.percentUsed,
    systemPromptLength: snapshot.systemPromptLength,
    historyMessageCount: snapshot.historyMessageCount,
    userMessageLength: snapshot.userMessageLength,
    contentHash: snapshot.contentHash,
    messages: snapshot.messages.map(m => ({
      role: m.role,
      contentLength: m.content?.length || 0,
      preview: m.content?.slice(0, 200) + (m.content?.length && m.content.length > 200 ? '...' : ''),
      hasToolCalls: !!m.tool_calls,
      name: m.name,
    })),
  }
}

// ============================================================================
// Tool Definitions
// ============================================================================

export const cassandraGetContextWindowDef: ToolDefinition = {
  name: 'cassandra_get_context_window',
  description: 'Get the latest context window snapshot with field projection support',
  parameters: {
    type: 'object',
    properties: {
      sessionId: { type: 'string', description: 'Session ID to get context window for' },
      includeFullContent: { type: 'boolean', description: 'Include full message content (may be large)', default: true },
      maxContentLength: { type: 'number', description: 'Max content length per message (default 10000)', default: 10000 },
      compact: { type: 'boolean', description: 'Return compact JSON', default: false },
    },
    required: ['sessionId'],
  },
  timeoutMs: 5_000,
}

export const cassandraGetContextHistoryDef: ToolDefinition = {
  name: 'cassandra_get_context_history',
  description: 'Get history of context window snapshots (cached summaries)',
  parameters: {
    type: 'object',
    properties: {
      sessionId: { type: 'string', description: 'Session ID' },
      since: { type: 'number', description: 'Timestamp to get snapshots since' },
      limit: { type: 'number', description: 'Maximum snapshots to return', default: 10 },
      noCache: { type: 'boolean', description: 'Bypass summary cache', default: false },
      compact: { type: 'boolean', description: 'Return compact JSON', default: false },
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
      compact: { type: 'boolean', description: 'Return compact JSON', default: false },
    },
    required: ['sessionId'],
  },
  timeoutMs: 5_000,
}

export const cassandraTailContextWindowDef: ToolDefinition = {
  name: 'cassandra_tail_context_window',
  description: 'Get SSE URL to tail context window updates in real-time',
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

// ============================================================================
// Handler Factories
// ============================================================================

export function makeCassandraGetContextWindowHandler(
  getDebugger: () => ContextWindowDebugger | null
): ToolHandler {
  return async (input, ctx) => {
    const sessionId = input['sessionId'] as string
    const includeFullContent = (input['includeFullContent'] as boolean) ?? true
    const maxContentLength = (input['maxContentLength'] as number) ?? 10000
    const compact = (input['compact'] as boolean) ?? false

    const startTime = Date.now()
    const ctxDebugger = getDebugger()

    if (!ctxDebugger) {
      return JSON.stringify({
        error: 'Context window debugging is not enabled on the daemon. Set debug.contextWindow.enabled: true in config.',
      })
    }

    const snapshot = ctxDebugger.getLatestSnapshot(sessionId)
    if (!snapshot) {
      return JSON.stringify({
        sessionId,
        error: 'No context window snapshot found. Has any turn been processed yet?',
      })
    }

    // Apply field projection
    const result = projectSnapshot(snapshot, includeFullContent, maxContentLength)

    ctx.logger.debug?.('[cassandra_get_context_window]', {
      sessionId,
      includeFullContent,
      messageCount: snapshot.messages.length,
      duration: `${Date.now() - startTime}ms`,
    })

    return JSON.stringify(result, null, compact ? undefined : 2)
  }
}

export function makeCassandraGetContextHistoryHandler(
  getDebugger: () => ContextWindowDebugger | null
): ToolHandler {
  return async (input, ctx) => {
    const sessionId = input['sessionId'] as string
    const since = input['since'] as number | undefined
    const limit = Math.min((input['limit'] as number) ?? 10, MAX_SNAPSHOTS_DEFAULT)
    const noCache = (input['noCache'] as boolean) ?? false
    const compact = (input['compact'] as boolean) ?? false

    const startTime = Date.now()
    const ctxDebugger = getDebugger()

    if (!ctxDebugger) {
      return JSON.stringify({ error: 'Context window debugging is not enabled on the daemon.' })
    }

    const allSnapshots = since
      ? ctxDebugger.getSnapshotsSince(sessionId, since)
      : ctxDebugger.getSnapshots(sessionId)

    if (allSnapshots.length === 0) {
      return JSON.stringify({ sessionId, snapshots: [], totalSnapshots: 0 })
    }

    // Check cache
    const latest = allSnapshots[allSnapshots.length - 1]
    let summaries: SnapshotSummary[]
    let fromCache = false

    if (!noCache && !since) {
      const cached = globalSummaryCache.get(sessionId, allSnapshots.length, latest.timestamp)
      if (cached) {
        summaries = cached.summaries.slice(-limit)
        fromCache = true
      } else {
        // Compute and cache
        summaries = Array.from(lazySnapshotSummaries(allSnapshots, limit))
        globalSummaryCache.set(sessionId, {
          summaries,
          snapshotCount: allSnapshots.length,
          lastSnapshotTimestamp: latest.timestamp,
          computedAt: Date.now(),
        })
      }
    } else {
      // No cache for filtered queries
      summaries = Array.from(lazySnapshotSummaries(allSnapshots, limit))
    }

    ctx.logger.debug?.('[cassandra_get_context_history]', {
      sessionId,
      totalSnapshots: allSnapshots.length,
      returned: summaries.length,
      fromCache,
      duration: `${Date.now() - startTime}ms`,
    })

    return JSON.stringify({
      sessionId,
      snapshots: summaries,
      totalSnapshots: allSnapshots.length,
      returned: summaries.length,
      fromCache,
    }, null, compact ? undefined : 2)
  }
}

export function makeCassandraGetContextStatsHandler(
  getDebugger: () => ContextWindowDebugger | null
): ToolHandler {
  return async (input, ctx) => {
    const sessionId = input['sessionId'] as string
    const compact = (input['compact'] as boolean) ?? false

    const startTime = Date.now()
    const ctxDebugger = getDebugger()

    if (!ctxDebugger) {
      return JSON.stringify({ error: 'Context window debugging is not enabled on the daemon.' })
    }

    const stats = ctxDebugger.getStats(sessionId)

    ctx.logger.debug?.('[cassandra_get_context_stats]', {
      sessionId,
      duration: `${Date.now() - startTime}ms`,
    })

    return JSON.stringify({ sessionId, stats }, null, compact ? undefined : 2)
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
      return JSON.stringify({ error: 'Context window debugging is not enabled on the daemon.' })
    }

    const latest = ctxDebugger.getLatestSnapshot(sessionId)

    return JSON.stringify({
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
    }, null, 2)
  }
}

// ============================================================================
// Registration Function
// ============================================================================

export function registerContextWindowTools(
  registry: any,
  getDebugger: () => ContextWindowDebugger | null
): void {
  registry.register(cassandraGetContextWindowDef, makeCassandraGetContextWindowHandler(getDebugger))
  registry.register(cassandraGetContextHistoryDef, makeCassandraGetContextHistoryHandler(getDebugger))
  registry.register(cassandraGetContextStatsDef, makeCassandraGetContextStatsHandler(getDebugger))
  registry.register(cassandraTailContextWindowDef, makeCassandraTailContextWindowHandler(getDebugger))
}

// Export cache for inspection
export { globalSummaryCache as summaryCache }
