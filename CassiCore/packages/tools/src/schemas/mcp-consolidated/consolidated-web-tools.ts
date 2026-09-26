#!/usr/bin/env node
/**
 * Consolidated Web Tools Module
 *
 * Merges web_fetch, web_search, and DuckDuckGo fetch_content into a single cassi_web tool.
 */

import { executeCassiCoreTool } from './tool-management.js';
import type { ToolRouter } from './serena-onboarding.js';
import type { ILogger } from '@cassicore/foundation';

/**
 * Consolidated web tool definition
 */
export const WEB_CONSOLIDATED_TOOL = {
  name: 'web',
  description: 'Web operations — fetch content from URLs, search the web, or extract page text. Use action parameter to select operation.\n\nUse this tool when you need to retrieve web content (fetch), search the internet for information (search), or extract readable text from a URL with pagination support (fetch_content). For browser automation with interactive elements (clicking, typing, screenshots), use cassi_browser instead.\n\nCommon actions: search (web search by query), fetch (get URL content as text), fetch_content (paginated text extraction from a URL).',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['fetch', 'search', 'fetch_content'],
        description: 'Web operation to perform: fetch (retrieve URL content), search (web search), or fetch_content (extract main text from a page with pagination)',
      },
      // fetch / fetch_content params
      url: {
        type: 'string',
        description: 'URL to fetch (for fetch and fetch_content actions)',
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
      // fetch_content params
      start_index: {
        type: 'number',
        description: 'Character offset to start reading from (for fetch_content action, default 0)',
      },
      max_length: {
        type: 'number',
        description: 'Maximum characters to return (for fetch_content action, default 8000)',
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
 * @param router - Optional tool router for external MCP tool dispatch (needed for fetch_content)
 */
export async function executeWebConsolidatedTool(
  baseUrl: string,
  args: any,
  logger: ILogger,
  router?: ToolRouter
): Promise<any> {
  const { action, ...restArgs } = args;

  if (!action) {
    throw new Error('Missing required parameter: action');
  }

  logger.debug('Executing consolidated web tool', { action });

  switch (action) {
    case 'fetch':
      return await executeCassiCoreTool(baseUrl, 'web_fetch', restArgs, logger);
    case 'search':
      return await executeCassiCoreTool(baseUrl, 'web_search', restArgs, logger);
    case 'fetch_content': {
      if (!router) {
        throw new Error('fetch_content action requires a tool router for DuckDuckGo dispatch');
      }
      const { url, start_index, max_length } = restArgs;
      if (!url) {
        throw new Error('Missing required parameter: url for fetch_content action');
      }
      return await router('duckduckgo_fetch_content', { url, start_index, max_length });
    }
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
