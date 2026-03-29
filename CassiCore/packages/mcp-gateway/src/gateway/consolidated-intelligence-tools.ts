#!/usr/bin/env node
/**
 * Consolidated Intelligence Tools Module
 *
 * Merges 14 intelligence tools into a single cassi_intelligence tool with action parameter:
 * - activity, thinker, subconscious, consciousness, trace, effectiveness, budget, evolution
 * - blindspots, snapshot, trust, consequences, dialectic, overview
 */

import { executeIntelligenceTool } from './intelligence-tools.js';
import { executeDialecticTool } from './dialectic-tools.js';
import type { ILogger } from '../../types/interfaces.js';
import { introspectSchemas } from '../../core/intelligence/code-analysis/index.js';
import { ContextFeedbackTracker } from '../../core/intelligence/code-analysis/index.js';

/**
 * Consolidated intelligence tool definition
 */
export const INTELLIGENCE_CONSOLIDATED_TOOL = {
  name: 'intelligence',
  description: 'Intelligence layer introspection — activity, thinker, subconscious, dialectic, trust, and more. Use action parameter to select operation.',
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

  // Map action to legacy tool name
  const validTools = new Set([
    'activity', 'thinker', 'subconscious', 'consciousness', 'trace',
    'effectiveness', 'budget', 'evolution', 'blindspots', 'snapshot',
    'trust', 'consequences',
  ]);

  if (!validTools.has(action)) {
    throw new Error(`Unknown intelligence action: ${action}. Valid actions: ${[...validTools].join(', ')}, dialectic, overview, schema, context_feedback`);
  }

  return await executeIntelligenceTool(baseUrl, action, restArgs, logger);
}

/**
 * Get the consolidated intelligence tool definition
 */
export function getIntelligenceConsolidatedTool(): typeof INTELLIGENCE_CONSOLIDATED_TOOL {
  return INTELLIGENCE_CONSOLIDATED_TOOL;
}
