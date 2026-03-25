#!/usr/bin/env node
/**
 * Core Tool Management Module
 * Basic file system and web tools
 */

import { fetchWithTimeout, formatJsonResponse } from './helpers.js';
import type { ILogger } from '../../types/interfaces.js';

const DEFAULT_FETCH_TIMEOUT_MS = 30_000;

/**
 * Tool definitions for core tools
 */
export const CORE_TOOLS = [
  {
    name: 'bash',
    description: 'Execute bash commands with timeout and output capture. Use for file operations, running tests, git commands, etc.',
    inputSchema: {
      type: 'object',
      properties: {
        command: {
          type: 'string',
          description: 'The bash command to execute',
        },
        cwd: {
          type: 'string',
          description: 'Working directory for the command (optional, defaults to current)',
        },
        timeout: {
          type: 'number',
          description: 'Timeout in milliseconds (optional, default 30000, max 120000)',
        },
      },
      required: ['command'],
    },
  },
  {
    name: 'read',
    description: 'Read a file from the filesystem. Returns content, size, and metadata.',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Absolute or relative path to the file',
        },
      },
      required: ['path'],
    },
  },
  {
    name: 'write',
    description: 'Write content to a file. Creates parent directories if needed.',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Absolute or relative path to write to',
        },
        content: {
          type: 'string',
          description: 'Content to write to the file',
        },
      },
      required: ['path', 'content'],
    },
  },
  {
    name: 'edit',
    description: 'Edit a file by replacing old text with new text. Fails if old text not found.',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Path to the file to edit',
        },
        oldText: {
          type: 'string',
          description: 'Exact text to replace (including whitespace)',
        },
        newText: {
          type: 'string',
          description: 'Replacement text',
        },
      },
      required: ['path', 'oldText', 'newText'],
    },
  },
  {
    name: 'mkdir',
    description: 'Create a directory (recursively if needed).',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Path to the directory to create',
        },
      },
      required: ['path'],
    },
  },
  {
    name: 'delete',
    description: 'Delete a file or directory (recursively).',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Path to delete',
        },
      },
      required: ['path'],
    },
  },
  {
    name: 'exists',
    description: 'Check if a file or directory exists. Returns existence and type.',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Path to check',
        },
      },
      required: ['path'],
    },
  },
  {
    name: 'web_fetch',
    description: 'Fetch content from a URL. Returns text content with HTML stripped.',
    inputSchema: {
      type: 'object',
      properties: {
        url: {
          type: 'string',
          description: 'URL to fetch',
        },
        timeoutMs: {
          type: 'number',
          description: 'Timeout in milliseconds (optional, default 30000)',
        },
      },
      required: ['url'],
    },
  },
  {
    name: 'web_search',
    description: 'Search the web for information. Returns search results with titles and snippets.',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query',
        },
        maxResults: {
          type: 'number',
          description: 'Maximum results to return (optional, default 5)',
        },
      },
      required: ['query'],
    },
  },
];

/**
 * Execute a core CassiCore tool
 * @dep callers: startHttp (mcp/cassicore-gateway.ts), routeToolCall (mcp/cassicore-gateway.ts)
 * @dep calls: get, fetchWithTimeout
 * @dep module: Mcp
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export async function executeCassiCoreTool(
  baseUrl: string,
  toolName: string,
  args: any,
  logger: ILogger
): Promise<any> {
  logger.info('Executing CassiCore tool', { tool: toolName, args });

  const knownTools = new Set([
    'bash', 'read', 'write', 'edit', 'mkdir', 'delete',
    'exists', 'web_fetch', 'web_search',
  ]);
  if (!knownTools.has(toolName)) {
    throw new Error(`Unknown tool: ${toolName}`);
  }

  // Primary path: route through ToolExecutor via /tools/execute.
  // This provides enrichment injection, permissions, trust scoring, and circuit breakers.
  try {
    const response = await fetchWithTimeout(`${baseUrl}/tools/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool: toolName, input: args }),
      timeoutMs: toolName === 'bash' ? 120_000 : DEFAULT_FETCH_TIMEOUT_MS,
    });

    if (response.ok) {
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('json')) {
        const result = await response.json();
        if (result && typeof result.content === 'string') {
          return { output: result.content, isError: result.isError ?? false, durationMs: result.durationMs };
        }
        return result;
      }
      return { output: await response.text() };
    }

    if (response.status === 503) {
      logger.debug('ToolExecutor unavailable, falling back to direct endpoint', { tool: toolName });
    } else {
      const error = await response.text().catch(() => '(unreadable body)');
      throw new Error(`CassiCore error: ${error}`);
    }
  } catch (error: any) {
    if (!String(error).includes('CassiCore error')) {
      logger.debug('ToolExecutor path failed, falling back', { tool: toolName, error: String(error) });
    } else {
      throw error;
    }
  }

  // Fallback: direct tool endpoints (no enrichment)
  const endpointMap: Record<string, string> = {
    bash: '/tools/bash',
    read: '/tools/read',
    write: '/tools/write',
    edit: '/tools/edit',
    mkdir: '/tools/mkdir',
    delete: '/tools/delete',
    exists: '/fs/exists',
    web_fetch: '/tools/web_fetch',
    web_search: '/tools/web_search',
  };

  const endpoint = endpointMap[toolName]!;
  const url = `${baseUrl}${endpoint}`;
  const readTools = ['read', 'exists'];
  const method = readTools.includes(toolName) ? 'GET' : 'POST';

  try {
    let response;
    if (method === 'GET') {
      const queryParams = new URLSearchParams(args).toString();
      response = await fetchWithTimeout(`${url}?${queryParams}`, {
        method: 'GET',
        timeoutMs: toolName === 'bash' ? 120_000 : DEFAULT_FETCH_TIMEOUT_MS,
      });
    } else {
      response = await fetchWithTimeout(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(args),
        timeoutMs: toolName === 'bash' ? 120_000 : DEFAULT_FETCH_TIMEOUT_MS,
      });
    }

    if (!response.ok) {
      const error = await response.text().catch(() => '(unreadable body)');
      throw new Error(`CassiCore error: ${error}`);
    }

    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('json')) {
      return await response.json();
    }
    const text = await response.text();
    return { output: text };
  } catch (error: any) {
    logger.error('Tool execution failed', { tool: toolName, error: String(error) });
    throw error;
  }
}

/**
 * Check if a tool is a core tool
 */
export function isCoreTool(toolName: string): boolean {
  return CORE_TOOLS.some(t => t.name === toolName);
}

/**
 * Get all core tool definitions
 * @dep callers: routeToolCall (mcp/cassicore-gateway.ts), getAllTools (mcp/cassicore-gateway.ts)
 * @dep flows: CreateHierarchyBridge → GetCoreTools (4/4)
 * @dep module: Gateway
 * @dep risk: LOW | 2 callers, 1 flow, 1 module
 */
export function getCoreTools(): Array<{
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}> {
  return CORE_TOOLS;
}
