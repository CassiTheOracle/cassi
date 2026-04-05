#!/usr/bin/env node
/**
 * Consolidated Session Tools Module
 *
 * Merges 9 session tools into a single cassi_session tool with action parameter:
 * - list, detail, prune, conversation, export
 * - resolve_ref, index, index_search, index_stats
 */

import { executeSessionTool } from './session-tools.js';
import type { ILogger } from '../../types/interfaces.js';

/**
 * Consolidated session tool definition
 */
export const SESSION_CONSOLIDATED_TOOL = {
  name: 'session',
  description: 'Session management — list, inspect, prune, export, and index operations. Use action parameter to select operation.\n\nUse this tool when you need to inspect daemon sessions (list/detail), recover conversation history (conversation/export), or manage the session index for granular referencing (index/index_search). For routine context retrieval at turn start, prefer cassi_enrich instead.\n\nCommon actions: list (see active sessions), detail (inspect one session), index_search (full-text search across indexed sessions), prune (clean up old sessions).',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: [
          'list', 'detail', 'prune', 'conversation', 'export',
          'resolve_ref', 'index', 'index_search', 'index_stats',
        ],
        description: 'Session operation to perform',
      },
      // Common params
      sessionId: {
        type: 'string',
        description: 'Session ID for operations targeting a specific session',
      },
      limit: {
        type: 'number',
        description: 'Maximum results to return (default 20)',
      },
      // session_detail params
      includeMessages: {
        type: 'boolean',
        description: 'Include message history (default false)',
      },
      messageLimit: {
        type: 'number',
        description: 'Maximum messages to return (default 20)',
      },
      // session_prune params
      maxAge: {
        type: 'string',
        description: 'Prune sessions older than this (e.g., "24h", "7d")',
      },
      channel: {
        type: 'string',
        description: 'Only prune sessions from this channel',
      },
      emptyOnly: {
        type: 'boolean',
        description: 'Only prune sessions with zero messages (default false)',
      },
      all: {
        type: 'boolean',
        description: 'Prune all sessions (dangerous, requires confirmation)',
      },
      // resolve_ref params
      ref: {
        type: 'string',
        description: 'Reference to resolve (e.g., "memory:key", "turn:123")',
      },
      // index_search params
      query: {
        type: 'string',
        description: 'Search query for index_search',
      },
      label: {
        type: 'string',
        description: 'Label for index operations',
      },
      // index_stats param (can be label or sessionId)
      labelOrSessionId: {
        type: 'string',
        description: 'Label or session ID for index stats',
      },
    },
    required: ['action'],
  },
};

/**
 * Tool name for routing
 */
export const SESSION_CONSOLIDATED_TOOL_NAME = 'session';

/**
 * Action to legacy tool name mapping
 */
const ACTION_TO_TOOL_NAME: Record<string, string> = {
  list: 'sessions',
  detail: 'session_detail',
  prune: 'session_prune',
  conversation: 'session_conversation',
  export: 'session_export',
  resolve_ref: 'resolve_ref',
  index: 'index_session',
  index_search: 'index_search',
  index_stats: 'index_stats',
};

/**
 * Execute the consolidated session tool
 *
 * @param baseUrl - CassiCore base URL
 * @param args - Tool arguments including action
 * @param logger - Logger instance
 */
export async function executeSessionConsolidatedTool(
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
    throw new Error(`Unknown session action: ${action}`);
  }

  logger.info('Executing consolidated session tool', { action, toolName, args: restArgs });

  return await executeSessionTool(baseUrl, toolName, restArgs, logger);
}

/**
 * Get the consolidated session tool definition
 */
export function getSessionConsolidatedTool(): typeof SESSION_CONSOLIDATED_TOOL {
  return SESSION_CONSOLIDATED_TOOL;
}
