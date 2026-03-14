/**
 * Consolidated Context Window Debugging Tools (Phase 2)
 *
 * Merges cassandra_get_context_window + cassandra_get_context_history + cassandra_get_context_stats
 * into unified inspection interface. Eliminates cassandra_tail_context_window (documented alternative).
 *
 * Preserves all caching behavior (SummaryCache with TTLs) from original implementation.
 */

import type { ContextWindowDebugger, ContextWindowSnapshot } from '../../events/context-window-debug.js'
import type { ToolDefinition, ToolHandler } from '../types.js'

// ============================================================================
// Constants
// ============================================================================

const SUMMARY_CACHE_TTL_MS = 2000  // 2 seconds
const MAX_SNAPSHOTS_DEFAULT = 50

// ============================================================================
// Summary Cache (preserved from original)
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
// Optimized Snapshot Processing (preserved from original)
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
// Field Projection for Messages (preserved from original)
// ============================================================================

function projectSnapshot(
  snapshot: ContextWindowSnapshot,
  includeFullContent: boolean,
  maxContentLength: number = 10000
): any {
  if (includeFullContent) {
    return {
      ...snapshot,
      messages: snapshot.messages.map(m => ({
        ...m,
        content: m.content?.length > maxContentLength
          ? `${m.content.slice(0, maxContentLength)}\n... [truncated]`
          : m.content,
      })),
    }
  }

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
// Consolidated Tool Definition
// ============================================================================

export const cassandraContextInspectDef: ToolDefinition = {
  name: 'cassandra_context_inspect',
  description:
    'Unified context window inspection tool. Use action parameter to choose operation:\n' +
    '- snapshot: Get latest context window snapshot with field projection\n' +
    '- history: Get history of context window snapshots (cached summaries)\n' +
    '- stats: Get statistics about context window usage\n\n' +
    'Replaces cassandra_get_context_window, cassandra_get_context_history, and cassandra_get_context_stats. ' +
    'For streaming, use HTTP endpoints directly (documented).',
  parameters: {
    type: 'object',
    properties: {
      sessionId: { type: 'string', description: 'Session ID to inspect' },
      action: {
        type: 'string',
        description: 'Inspection action',
        enum: ['snapshot', 'history', 'stats'],
        default: 'snapshot',
      },
      // Options for 'snapshot' action
      includeFullContent: { type: 'boolean', description: 'Include full message content (for snapshot)', default: true },
      maxContentLength: { type: 'number', description: 'Max content length per message (for snapshot)', default: 10000 },
      // Options for 'history' action
      since: { type: 'number', description: 'Timestamp to get snapshots since (for history)' },
      limit: { type: 'number', description: 'Maximum snapshots to return (for history)', default: 10 },
      noCache: { type: 'boolean', description: 'Bypass summary cache (for history)', default: false },
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

export function makeCassandraContextInspectHandler(
  getDebugger: () => ContextWindowDebugger | null
): ToolHandler {
  return async (input, ctx) => {
    const sessionId = input['sessionId'] as string
    const action = (input['action'] as string) ?? 'snapshot'
    const compact = (input['compact'] as boolean) ?? false

    const startTime = Date.now()
    const ctxDebugger = getDebugger()

    if (!ctxDebugger) {
      return JSON.stringify({
        error: 'Context window debugging is not enabled on the daemon. Set debug.contextWindow.enabled: true in config.',
      })
    }

    let result: any

    if (action === 'snapshot') {
      const includeFullContent = (input['includeFullContent'] as boolean) ?? true
      const maxContentLength = (input['maxContentLength'] as number) ?? 10000

      const snapshot = ctxDebugger.getLatestSnapshot(sessionId)
      if (!snapshot) {
        return JSON.stringify({
          sessionId,
          error: 'No context window snapshot found. Has any turn been processed yet?',
        })
      }

      result = projectSnapshot(snapshot, includeFullContent, maxContentLength)

      ctx.logger.debug?.('[cassandra_context_inspect.snapshot]', {
        sessionId,
        includeFullContent,
        messageCount: snapshot.messages.length,
        duration: `${Date.now() - startTime}ms`,
      })
    } else if (action === 'history') {
      const since = input['since'] as number | undefined
      const limit = Math.min((input['limit'] as number) ?? 10, MAX_SNAPSHOTS_DEFAULT)
      const noCache = (input['noCache'] as boolean) ?? false

      const allSnapshots = since
        ? ctxDebugger.getSnapshotsSince(sessionId, since)
        : ctxDebugger.getSnapshots(sessionId)

      if (allSnapshots.length === 0) {
        result = { sessionId, snapshots: [], totalSnapshots: 0 }
      } else {
        const latest = allSnapshots[allSnapshots.length - 1]
        let summaries: SnapshotSummary[]
        let fromCache = false

        if (!noCache && !since) {
          const cached = globalSummaryCache.get(sessionId, allSnapshots.length, latest.timestamp)
          if (cached) {
            summaries = cached.summaries.slice(-limit)
            fromCache = true
          } else {
            summaries = Array.from(lazySnapshotSummaries(allSnapshots, limit))
            globalSummaryCache.set(sessionId, {
              summaries,
              snapshotCount: allSnapshots.length,
              lastSnapshotTimestamp: latest.timestamp,
              computedAt: Date.now(),
            })
          }
        } else {
          summaries = Array.from(lazySnapshotSummaries(allSnapshots, limit))
        }

        result = {
          sessionId,
          snapshots: summaries,
          totalSnapshots: allSnapshots.length,
          returned: summaries.length,
          fromCache,
        }

        ctx.logger.debug?.('[cassandra_context_inspect.history]', {
          sessionId,
          totalSnapshots: allSnapshots.length,
          returned: summaries.length,
          fromCache,
          duration: `${Date.now() - startTime}ms`,
        })
      }
    } else if (action === 'stats') {
      const stats = ctxDebugger.getStats(sessionId)
      result = { sessionId, stats }

      ctx.logger.debug?.('[cassandra_context_inspect.stats]', {
        sessionId,
        duration: `${Date.now() - startTime}ms`,
      })
    } else {
      return JSON.stringify({ error: `Unknown action "${action}". Use "snapshot", "history", or "stats".` })
    }

    return JSON.stringify(result, null, compact ? undefined : 2)
  }
}

// ============================================================================
// Registration Function
// ============================================================================

export function registerContextWindowTools(
  registry: any,
  getDebugger: () => ContextWindowDebugger | null
): void {
  registry.register(cassandraContextInspectDef, makeCassandraContextInspectHandler(getDebugger))
}

// Export cache for inspection
export { globalSummaryCache as summaryCache }
