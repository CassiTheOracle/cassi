#!/usr/bin/env node
/**
 * Consolidated Intelligence Tools Module
 *
 * Merges intelligence tools into a single cassi_intelligence tool with action parameter:
 * - activity, thinker, subconscious, consciousness, trace, effectiveness, budget, evolution
 * - blindspots, snapshot, trust, consequences, dialectic, overview
 * - schema, context_feedback
 * - meditation_status, meditation_start, meditation_stop, meditation_live, meditation_live_full,
 *   meditation_insights, meditation_self_awareness, meditation_prompts, meditation_leaderboard,
 *   meditation_scores, meditation_evolution, meditation_search
 * - cortex_stats, cortex_oscillation, cortex_region, cortex_signal, cortex_search,
 *   cortex_consolidated, cortex_fading, cortex_session, cortex_tract
 */

import { executeIntelligenceTool } from './intelligence-tools.js';
import { executeDialecticTool } from './dialectic-tools.js';
import { fetchWithTimeout, fetchIntelligence } from './helpers.js';
import type { ILogger } from '../../types/interfaces.js';
import { introspectSchemas } from '../../core/intelligence/code-analysis/index.js';
import { ContextFeedbackTracker } from '../../core/intelligence/code-analysis/index.js';

/**
 * Consolidated intelligence tool definition
 */
export const INTELLIGENCE_CONSOLIDATED_TOOL = {
  name: 'intelligence',
  description: 'Intelligence layer introspection — activity, thinker, subconscious, dialectic, trust, cortex, and more. Use action parameter to select operation.\n\nUse this tool when you need to understand what the intelligence layer is doing (activity), inspect cognitive state (thinker/subconscious), trace why a response was shaped a certain way (trace), check trust scores (trust), introspect database schemas (schema), observe the cortical field (cortex_stats, cortex_search, cortex_region), or inspect meditation (meditation_status, meditation_live, meditation_leaderboard).\n\nCommon actions: activity (high-level dashboard), schema (database introspection), trust (permission/autonomy scores), trace (forensic turn analysis), context_feedback (record whether assembled context helped), cortex_stats (cortical field dashboard), cortex_search (find signals by type/state/author/tags/content).',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: [
          'activity', 'thinker', 'subconscious', 'consciousness', 'trace',
          'effectiveness', 'budget', 'evolution', 'blindspots', 'snapshot',
          'trust', 'consequences', 'dialectic', 'overview',
          'schema', 'context_feedback',
          'meditation_status', 'meditation_start', 'meditation_stop',
          'meditation_live', 'meditation_live_full', 'meditation_insights',
          'meditation_self_awareness', 'meditation_prompts', 'meditation_leaderboard',
          'meditation_scores', 'meditation_evolution', 'meditation_search',
          'cortex_stats', 'cortex_oscillation', 'cortex_region', 'cortex_signal',
          'cortex_search', 'cortex_consolidated', 'cortex_fading',
          'cortex_session', 'cortex_tract',
        ],
        description: 'Intelligence operation to perform',
      },
      // Common params
      sessionId: {
        type: 'string',
        description: 'Session ID to inspect (optional, defaults to most recent active session)',
      },
      mode: {
        type: 'string',
        enum: ['brief', 'full'],
        description: 'Output mode: "brief" for summary (default), "full" for detailed dashboard',
      },
      limit: {
        type: 'number',
        description: 'Number of results to show (default varies by action)',
      },
      // trace params
      since: {
        type: 'string',
        description: 'ISO timestamp for trace start time',
      },
      // effectiveness params
      module: {
        type: 'string',
        description: 'Filter effectiveness by module name',
      },
      // budget params
      tier: {
        type: 'string',
        enum: ['critical', 'normal', 'background', 'all'],
        description: 'Budget tier to inspect',
      },
      // evolution params
      includeHistory: {
        type: 'boolean',
        description: 'Include full evolution history',
      },
      // snapshot params
      teamId: {
        type: 'string',
        description: 'Focus on a specific team for snapshot',
      },
      includeMessages: {
        type: 'boolean',
        description: 'Include recent agent messages in snapshot (default: true)',
      },
      messageLimit: {
        type: 'number',
        description: 'Max recent messages per agent in snapshot (default: 5)',
      },
      // trust params
      domain: {
        type: 'string',
        description: 'Specific trust domain to inspect (e.g., "file-read", "shell-execution")',
      },
      // schema params
      database: {
        type: 'string',
        description: 'Filter to specific database name (for schema action)',
      },
      table: {
        type: 'string',
        description: 'Filter to specific table name (for schema action)',
      },
      // cortex params
      signalId: {
        type: 'string',
        description: 'Signal ID (for cortex_signal action)',
      },
      region: {
        type: 'string',
        description: 'Region name (for cortex_region action, or cortex_search filter)',
      },
      signalType: {
        type: 'string',
        description: 'Signal type filter (for cortex_search: perception, association, concern, decision, action, request, anomaly, insight)',
      },
      signalState: {
        type: 'string',
        description: 'Signal state filter (for cortex_search: active, fading, consolidated, decayed)',
      },
      author: {
        type: 'string',
        description: 'Author filter (for cortex_search)',
      },
      tags: {
        type: 'string',
        description: 'Comma-separated tags filter (for cortex_search)',
      },
      content: {
        type: 'string',
        description: 'Content substring filter (for cortex_search)',
      },
      tractId: {
        type: 'string',
        description: 'Tract ID (for cortex_tract action)',
      },
      // meditation params
      posture: {
        type: 'string',
        description: 'Filter by posture (e.g., yang, yin, executive). For meditation_start: style (passive, active, focused, reflective) or "follow-up" to seed from previous meditation insights.',
      },
    },
    required: ['action'],
  },
};

/**
 * Tool name for routing
 */
export const INTELLIGENCE_CONSOLIDATED_TOOL_NAME = 'intelligence';

/**
 * Execute the consolidated intelligence tool
 *
 * @param baseUrl - CassiCore base URL
 * @param args - Tool arguments including action
 * @param logger - Logger instance
 */
export async function executeIntelligenceConsolidatedTool(
  baseUrl: string,
  args: any,
  logger: ILogger
): Promise<any> {
  const { action, ...restArgs } = args;

  if (!action) {
    throw new Error('Missing required parameter: action');
  }

  logger.info('Executing consolidated intelligence tool', { action, args: restArgs });

  // Handle dialectic separately (it's in a different module)
  if (action === 'dialectic') {
    return await executeDialecticTool(baseUrl, 'dialectic', restArgs, logger);
  }

  // Handle overview as a special composite action
  if (action === 'overview') {
    return await executeIntelligenceTool(baseUrl, '_1', restArgs, logger);
  }

  // Handle schema introspection (runs locally, no admin API needed)
  if (action === 'schema') {
    const result = introspectSchemas(logger, {
      database: restArgs.database,
      table: restArgs.table,
    });
    return {
      output: `**CassiCore Internal Databases** (${result.databases.length} databases, ${result.totalTables} tables, ${result.totalRows.toLocaleString()} rows)\n\n` +
        result.databases.map(db =>
          `### ${db.name} (${(db.sizeBytes / 1024).toFixed(1)} KB)\n` +
          `Path: \`${db.path}\`\n` +
          db.tables.map(t =>
            `- **${t.name}** (${t.rowCount >= 0 ? t.rowCount.toLocaleString() + ' rows' : 'n/a'}): ${t.columns.map(c => `${c.name}:${c.type}`).join(', ')}`
          ).join('\n')
        ).join('\n\n'),
      ...result,
    };
  }

  // Handle context feedback stats
  if (action === 'context_feedback') {
    try {
      const tracker = new ContextFeedbackTracker(logger);
      const stats = tracker.getStats();
      const scores = tracker.getEffectivenessScores();
      const recent = tracker.getRecent(restArgs.limit || 10);
      tracker.close();

      return {
        output: `**Context Feedback Stats**\n\n` +
          `Total records: ${stats.totalRecords} | Useful rate: ${(stats.usefulRate * 100).toFixed(1)}%\n\n` +
          `By mode:\n` +
          Object.entries(stats.byMode).map(([mode, data]) =>
            `- ${mode}: ${data.count} records, ${(data.usefulRate * 100).toFixed(1)}% useful`
          ).join('\n') +
          `\n\nBayesian scores:\n` +
          scores.map(s =>
            `- ${s.mode}/${s.specificityBucket}: mean=${s.bayesMean} (n=${s.sampleCount})`
          ).join('\n') +
          `\n\nRecent (${recent.length}):\n` +
          recent.slice(0, 5).map(r =>
            `- ${r.contextMode} | specificity=${r.specificityScore} | useful=${r.wasUseful} | "${r.queryText.slice(0, 60)}"`
          ).join('\n'),
        stats,
        scores,
        recentCount: recent.length,
      };
    } catch (err) {
      return { output: `Context feedback unavailable: ${String(err)}` };
    }
  }

  // Meditation actions — routed to admin API /meditation/* endpoints
  if (action === 'meditation_status') {
    return await fetchIntelligence(baseUrl, '/meditation/status')
  }
  if (action === 'meditation_start') {
    const bodyObj: Record<string, unknown> = {}
    if (restArgs.posture === 'follow-up') {
      bodyObj.followUp = true
    } else if (restArgs.posture) {
      bodyObj.style = restArgs.posture
    }
    const res = await fetchWithTimeout(`${baseUrl}/meditation/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bodyObj),
    })
    return await res.json()
  }
  if (action === 'meditation_stop') {
    const res = await fetchWithTimeout(`${baseUrl}/meditation/stop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    })
    return await res.json()
  }
  if (action === 'meditation_live') {
    return await fetchIntelligence(baseUrl, '/meditation/live')
  }
  if (action === 'meditation_live_full') {
    return await fetchIntelligence(baseUrl, '/meditation/live/full')
  }
  if (action === 'meditation_insights') {
    return await fetchIntelligence(baseUrl, '/meditation/insights')
  }
  if (action === 'meditation_self_awareness') {
    return await fetchIntelligence(baseUrl, '/meditation/self-awareness')
  }
  if (action === 'meditation_prompts') {
    return await fetchIntelligence(baseUrl, '/meditation/prompts')
  }
  if (action === 'meditation_leaderboard') {
    return await fetchIntelligence(baseUrl, '/meditation/leaderboard')
  }
  if (action === 'meditation_scores') {
    const limit = restArgs.limit ?? 20
    return await fetchIntelligence(baseUrl, `/meditation/scores?limit=${limit}`)
  }
  if (action === 'meditation_evolution') {
    return await fetchIntelligence(baseUrl, '/meditation/evolution')
  }
  if (action === 'meditation_search') {
    if (!restArgs.content) throw new Error('content parameter required for meditation_search (search query)')
    const limit = restArgs.limit ?? 20
    return await fetchIntelligence(baseUrl, `/meditation/search?q=${encodeURIComponent(restArgs.content)}&limit=${limit}`)
  }

  // Cortex observability actions — routed to admin API /cortex/* endpoints
  if (action === 'cortex_stats') {
    return await fetchIntelligence(baseUrl, '/cortex/stats')
  }
  if (action === 'cortex_oscillation') {
    const limit = restArgs.limit ?? 50
    return await fetchIntelligence(baseUrl, `/cortex/oscillation/history?limit=${limit}`)
  }
  if (action === 'cortex_region') {
    if (!restArgs.region) throw new Error('region parameter required for cortex_region action')
    return await fetchIntelligence(baseUrl, `/cortex/region/${encodeURIComponent(restArgs.region)}`)
  }
  if (action === 'cortex_signal') {
    if (!restArgs.signalId) throw new Error('signalId parameter required for cortex_signal action')
    return await fetchIntelligence(baseUrl, `/cortex/signal/${encodeURIComponent(restArgs.signalId)}`)
  }
  if (action === 'cortex_search') {
    const params = new URLSearchParams()
    if (restArgs.region) params.set('region', restArgs.region)
    if (restArgs.signalType) params.set('type', restArgs.signalType)
    if (restArgs.signalState) params.set('state', restArgs.signalState)
    if (restArgs.author) params.set('author', restArgs.author)
    if (restArgs.tags) params.set('tags', restArgs.tags)
    if (restArgs.sessionId) params.set('sessionId', restArgs.sessionId)
    if (restArgs.content) params.set('content', restArgs.content)
    if (restArgs.limit) params.set('limit', String(restArgs.limit))
    const qs = params.toString()
    return await fetchIntelligence(baseUrl, `/cortex/signals/search${qs ? '?' + qs : ''}`)
  }
  if (action === 'cortex_consolidated') {
    const limit = restArgs.limit ?? 20
    return await fetchIntelligence(baseUrl, `/cortex/signals/consolidated?limit=${limit}`)
  }
  if (action === 'cortex_fading') {
    const limit = restArgs.limit ?? 20
    return await fetchIntelligence(baseUrl, `/cortex/signals/fading?limit=${limit}`)
  }
  if (action === 'cortex_session') {
    if (!restArgs.sessionId) throw new Error('sessionId parameter required for cortex_session action')
    return await fetchIntelligence(baseUrl, `/cortex/session/${encodeURIComponent(restArgs.sessionId)}`)
  }
  if (action === 'cortex_tract') {
    if (!restArgs.tractId) throw new Error('tractId parameter required for cortex_tract action')
    return await fetchIntelligence(baseUrl, `/cortex/tract/${encodeURIComponent(restArgs.tractId)}`)
  }

  // Map action to legacy tool name
  const validTools = new Set([
    'activity', 'thinker', 'subconscious', 'consciousness', 'trace',
    'effectiveness', 'budget', 'evolution', 'blindspots', 'snapshot',
    'trust', 'consequences',
  ]);

  if (!validTools.has(action)) {
    throw new Error(`Unknown intelligence action: ${action}. Valid actions: ${[...validTools].join(', ')}, dialectic, overview, schema, context_feedback, meditation_status/start/stop/live/live_full/insights/self_awareness/prompts/leaderboard/scores/evolution/search, cortex_*`);
  }

  return await executeIntelligenceTool(baseUrl, action, restArgs, logger);
}

/**
 * Get the consolidated intelligence tool definition
 */
export function getIntelligenceConsolidatedTool(): typeof INTELLIGENCE_CONSOLIDATED_TOOL {
  return INTELLIGENCE_CONSOLIDATED_TOOL;
}
