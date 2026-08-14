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
    description: 'Execute bash commands with timeout and output capture. Use for running tests, git commands, build commands, and system operations. For reading/writing/editing files, prefer cassi_file or the dedicated read/write/edit tools instead.',
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
    description: 'Read a file from the filesystem. Returns content, size, and metadata. Use for quick single-file reads. For advanced file operations (regex search, directory listing, pagination through large files), use cassi_file instead.',
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
    description: 'Write content to a file. Creates parent directories if needed. Use for creating new files or fully overwriting existing ones. For partial text replacement within a file, use the edit tool or cassi_file with action=edit instead.',
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
    description: 'Edit a file by replacing old text with new text. Fails if old text not found. Use for targeted text replacements within a file. For regex-based replacements or multi-occurrence edits, use cassi_file with action=edit and mode=regex.',
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
          items: {
            type: 'object',
            properties: {
              content: { type: 'string', description: 'Brief description of the task' },
              status: { type: 'string', enum: ['pending', 'in_progress', 'completed'], description: 'Current status of the task' },
              priority: { type: 'string', enum: ['high', 'medium', 'low'], description: 'Priority level of the task' },
            },
            required: ['content', 'status', 'priority'],
          },
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
    'session, session_stop, dev_start, dev_stop, inject_overlay, browser_open, ingest_bugs',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: [
          'session', 'session_stop',
          'start', 'stop', 'status', 'poll', 'list', 'implement_next', 'mark_done', 'discard',
          'dev_start', 'dev_stop', 'inject_overlay', 'browser_open',
          'ingest_bugs',
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
 * Skill intelligence tool — effectiveness tracking and pattern detection.
 */
export const SKILL_INTELLIGENCE_TOOL = {
  name: 'skill_intelligence',
  description:
    'Skill effectiveness tracking and intelligence. Record outcomes after using skills, ' +
    'view stats, detect patterns, and get the effectiveness feed.\n\n' +
    'Actions: outcome, stats, patterns, feed',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['outcome', 'stats', 'patterns', 'feed'],
        description: 'Action to perform',
      },
      skillName: { type: 'string', description: 'Skill name (for outcome)' },
      outcome: { type: 'string', enum: ['success', 'partial', 'failure'], description: 'Outcome (for outcome)' },
      note: { type: 'string', description: 'Outcome note' },
      taskDomain: { type: 'string', description: 'Task domain' },
      days: { type: 'number', description: 'Lookback days (default 30)' },
    },
    required: ['action'],
  },
};

/**
 * Workflow tool — agent-facing workflow management.
 */
export const WORKFLOW_TOOL = {
  name: 'workflow',
  description:
    'Agent workflow system — list, run, resume, and manage multi-step workflows. ' +
    'Chain tools, skills, Constellation projects, and Helix sessions into composable pipelines.\n\n' +
    'Actions: list, run, status, resume, cancel, runs, save_def, load_def, list_defs, delete_def',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['list', 'run', 'status', 'resume', 'cancel', 'runs', 'save_def', 'load_def', 'list_defs', 'delete_def'],
        description: 'Action to perform',
      },
      workflowId: { type: 'string', description: 'Workflow definition id (for run/resume/save_def/load_def/delete_def)' },
      runId: { type: 'string', description: 'Workflow run id (for status/resume/cancel)' },
      input: { type: 'string', description: 'JSON-encoded input data (for run/resume)' },
      status: {
        type: 'string',
        enum: ['pending', 'running', 'completed', 'failed', 'suspended', 'cancelled'],
        description: 'Filter by status (for runs)',
      },
      limit: { type: 'string', description: 'Max results (for runs/list_defs, default: 20)' },
      name: { type: 'string', description: 'Workflow definition name (for save_def)' },
      version: { type: 'string', description: 'Semantic version (for save_def/load_def/delete_def, e.g. "1.0.0")' },
      description: { type: 'string', description: 'Workflow definition description (for save_def)' },
      tags: { type: 'string', description: 'Comma-separated tags (for save_def/list_defs)' },
      enabled: { type: 'string', description: 'Whether enabled (for save_def/list_defs, "true"/"false")' },
      nodeGraph: { type: 'string', description: 'JSON-encoded node graph (for save_def)' },
    },
    required: ['action'],
  },
};

/**
 * Execute a core CassiCore tool
 * @dep callers: executeArtifactConsolidatedTool (mcp/gateway/consolidated-file-tools.ts), executeWebConsolidatedTool (mcp/gateway/consolidated-web-tools.ts), startHttp (mcp/cassicore-gateway.ts), routeToolCall (mcp/cassicore-gateway.ts)
 * @dep calls: fetchWithTimeout, has
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
    'exists', 'web_fetch', 'web_search', 'todo_write', 'vybit', 'skill_intelligence', 'workflow',
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
 * @dep callers: isCoreToolName (mcp/cassicore-gateway.ts), getAllTools (mcp/cassicore-gateway.ts)
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
