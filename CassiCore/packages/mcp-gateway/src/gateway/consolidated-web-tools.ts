#!/usr/bin/env node
/**
 * Consolidated Web Tools Module
 *
 * Merges web_fetch and web_search into a single cassi_web tool with action parameter.
 */

import { executeCassiCoreTool } from './tool-management.js';
import type { ILogger } from '../../types/interfaces.js';

/**
 * Consolidated web tool definition
 */
export const WEB_CONSOLIDATED_TOOL = {
  name: 'web',
  description: 'Web operations — fetch content from URLs or search the web. Use action parameter to select operation.',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['fetch', 'search'],
        description: 'Web operation to perform: fetch (retrieve URL content) or search (web search)',
      },
      // fetch params
      url: {
        type: 'string',
        description: 'URL to fetch (for fetch action)',
      },
      // search params
      query: {
        type: 'string',
        description: 'Search query (for search action)',
      },
      // Common params
      timeoutMs: {
        type: 'number',
        description: 'Timeout in milliseconds (default 30000)',
      },
      maxResults: {
        type: 'number',
        description: 'Maximum results to return (for search action, default 5)',
      },
    },
    required: ['action'],
  },
};

/**
 * Tool name for routing
 */
export const WEB_CONSOLIDATED_TOOL_NAME = 'web';

/**
 * Execute the consolidated web tool
 *
 * @param baseUrl - CassiCore base URL
 * @param args - Tool arguments including action
 * @param logger - Logger instance
 */
export async function executeWebConsolidatedTool(
  baseUrl: string,
  args: any,
  logger: ILogger
): Promise<any> {
  const { action, ...restArgs } = args;

  if (!action) {
    throw new Error('Missing required parameter: action');
  }

  logger.info('Executing consolidated web tool', { action, args: restArgs });

  switch (action) {
    case 'fetch':
      return await executeCassiCoreTool(baseUrl, 'web_fetch', restArgs, logger);
    case 'search':
      return await executeCassiCoreTool(baseUrl, 'web_search', restArgs, logger);
    default:
      throw new Error(`Unknown web action: ${action}`);
  }
}

/**
 * Get the consolidated web tool definition
 */
export function getWebConsolidatedTool(): typeof WEB_CONSOLIDATED_TOOL {
  return WEB_CONSOLIDATED_TOOL;
}
