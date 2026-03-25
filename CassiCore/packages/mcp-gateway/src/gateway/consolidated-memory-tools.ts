#!/usr/bin/env node
/**
 * Consolidated Memory Tools Module
 *
 * Merges 14 memory tools into a single cassi_memory tool with action parameter:
 * - store, search, recent, delete
 * - kv_get, kv_set, kv_del, stats
 * - archive_search, archive_get, archive_related, archive_recent
 * - browse, universal_search
 */

import { executeMemoryTool } from './memory-tools.js';
import type { ILogger } from '../../types/interfaces.js';

/**
 * Consolidated memory tool definition
 */
export const MEMORY_CONSOLIDATED_TOOL = {
  name: 'memory',
  description: 'Memory operations — store, search, KV operations, archive access, and universal search. Use action parameter to select operation.',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: [
          'store', 'search', 'recent', 'delete',
          'kv_get', 'kv_set', 'kv_del', 'stats',
          'archive_search', 'archive_get', 'archive_related', 'archive_recent',
          'browse', 'universal_search',
        ],
        description: 'Memory operation to perform',
      },
      // memory_store params
      key: {
        type: 'string',
        description: 'Unique key/identifier for memory_store or kv_set/kv_get/kv_del',
      },
      content: {
        type: 'string',
        description: 'Content to store (for store action)',
      },
      tags: {
        type: 'array',
        items: { type: 'string' },
        description: 'Optional tags for categorization',
      },
      // memory_search / archive_search params
      query: {
        type: 'string',
        description: 'Search query (supports FTS5 syntax)',
      },
      // memory_delete / archive_get params
      id: {
        type: 'string',
        description: 'Memory/archive entry ID',
      },
      // archive_related params
      sessionId: {
        type: 'string',
        description: 'Session ID for archive_related',
      },
      // universal_search params
      includeMemories: {
        type: 'boolean',
        description: 'Include memory store results (default true)',
      },
      includeArchives: {
        type: 'boolean',
        description: 'Include archive results (default true)',
      },
      // Common params
      limit: {
        type: 'number',
        description: 'Maximum results to return (default 10)',
      },
      // kv_set params
      value: {
        description: 'Value to store (for kv_set)',
      },
      ttl: {
        type: 'number',
        description: 'Time-to-live in seconds (for kv_set)',
      },
      // browse params
      path: {
        type: 'string',
        description: 'URL path to browse (for browse action)',
      },
    },
    required: ['action'],
  },
};

/**
 * Tool name for routing
 */
export const MEMORY_CONSOLIDATED_TOOL_NAME = 'memory';

/**
 * Action to legacy tool name mapping
 */
const ACTION_TO_TOOL_NAME: Record<string, string> = {
  store: 'memory_store',
  search: 'memory_search',
  recent: 'memory_recent',
  delete: 'memory_delete',
  kv_get: 'memory_kv_get',
  kv_set: 'memory_kv_set',
  kv_del: 'memory_kv_del',
  stats: 'memory_stats',
  archive_search: 'archive_search',
  archive_get: 'archive_get',
  archive_related: 'archive_related',
  archive_recent: 'archive_recent',
  browse: 'browse',
  universal_search: 'universal_search',
};

/**
 * Execute the consolidated memory tool
 *
 * @param baseUrl - CassiCore base URL
 * @param args - Tool arguments including action
 * @param logger - Logger instance
 */
export async function executeMemoryConsolidatedTool(
  baseUrl: string,
  args: any,
  logger: ILogger
): Promise<any> {
  const { action, ...restArgs } = args;

  if (!action) {
    throw new Error('Missing required parameter: action');
  }

  const toolName = ACTION_TO_TOOL_NAME[action];
  if (!toolName) {
    throw new Error(`Unknown memory action: ${action}`);
  }

  logger.info('Executing consolidated memory tool', { action, toolName, args: restArgs });

  return await executeMemoryTool(baseUrl, toolName, restArgs, logger);
}

/**
 * Get the consolidated memory tool definition
 */
export function getMemoryConsolidatedTool(): typeof MEMORY_CONSOLIDATED_TOOL {
  return MEMORY_CONSOLIDATED_TOOL;
}
