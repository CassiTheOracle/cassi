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
  {
    name: 'todo_write',
    description: 'Update the structured task list for the current session. Track multi-step work, plan tasks, and show progress. Send the FULL todo list on every call.',
    inputSchema: {
      type: 'object',
      properties: {
        todos: {
          type: 'array',
          description: 'The complete updated todo list. Each item: { content: string, status: "pending"|"in_progress"|"completed", priority: "high"|"medium"|"low" }',
        },
      },
      required: ['todos'],
    },
  },
];

/**
 * VyBit visual editing tool — exposed separately from core tools but
 * routed through the same ToolExecutor pathway.
 */
export const VYBIT_TOOL = {
  name: 'vybit',
  description:
    'Visual browser editing via VyBit. Start a VyBit server, poll for visual changes ' +
    '(Tailwind edits, component drops, design sketches, bug reports), and implement them in code.\n\n' +
    'Actions: start, stop, status, poll, list, implement_next, mark_done, discard, ' +
    'session, session_stop, dev_start, dev_stop, inject_overlay, browser_open',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: [
          'session', 'session_stop',
          'start', 'stop', 'status', 'poll', 'list', 'implement_next', 'mark_done', 'discard',
          'dev_start', 'dev_stop', 'inject_overlay', 'browser_open',
        ],
        description: 'Action to perform',
      },
      projectPath: {
        type: 'string',
        description: 'Absolute path to the target project (required for "start")',
      },
      port: {
        type: 'string',
        description: 'VyBit server port (default: 3333, used with "start")',
      },
      commitId: {
        type: 'string',
        description: 'Commit ID to mark as done (required for "mark_done")',
      },
      results: {
        type: 'string',
        description: 'JSON array of { patchId, success, error? } results (for "mark_done")',
      },
      filter: {
        type: 'string',
        description: 'Filter by status: staged, committed, implementing, implemented, error (for "list")',
      },
    },
    required: ['action'],
  },
};

/**
 * Execute a core CassiCore tool
 * @dep callers: routeToolCall (mcp/cassicore-gateway.ts), startHttp (mcp/cassicore-gateway.ts), executeWebConsolidatedTool (mcp/gateway/consolidated-web-tools.ts), executeArtifactConsolidatedTool (mcp/gateway/consolidated-file-tools.ts)
 * @dep calls: has, fetchWithTimeout
 * @dep module: Gateway
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
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
    'exists', 'web_fetch', 'web_search', 'todo_write', 'vybit',
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
 * @dep callers: getAllTools (mcp/cassicore-gateway.ts), routeToolCall (mcp/cassicore-gateway.ts)
 * @dep module: Mcp
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function getCoreTools(): Array<{
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}> {
  return CORE_TOOLS;
}
