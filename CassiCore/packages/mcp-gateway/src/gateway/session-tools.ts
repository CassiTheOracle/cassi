#!/usr/bin/env node
/**
 * Session Tools Module
 * Session management, conversation retrieval, and indexing
 */

import { fetchWithTimeout } from './helpers.js';
import type { ILogger } from '../../types/interfaces.js';

/**
 * Tool definitions for session tools
 */
export const SESSION_TOOLS = [
  {
    name: 'sessions',
    description: 'List all active CassiCore daemon sessions with their channel, sender, message count, and last activity.',
    inputSchema: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Maximum sessions to return (default 20)',
        },
      },
    },
  },
  {
    name: 'session_detail',
    description: 'Get detailed information about a specific session, including its messages.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: {
          type: 'string',
          description: 'Session ID to inspect',
        },
        includeMessages: {
          type: 'boolean',
          description: 'Include message history (default false)',
        },
        messageLimit: {
          type: 'number',
          description: 'Maximum messages to return (default 20)',
        },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'session_prune',
    description: 'Prune old, empty, or inactive sessions from the daemon.',
    inputSchema: {
      type: 'object',
      properties: {
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
      },
    },
  },
  {
    name: 'session_conversation',
    description: 'Retrieve the full archived conversation thread for a session, including thinking blocks.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'Session ID' },
        limit: { type: 'number', description: 'Max turns to return (default 50)' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'session_export',
    description: 'Export a complete session as structured JSON (conversation + thinking + metadata).',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'Session ID to export' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'resolve_ref',
    description: 'Resolve a compact session ref (e.g. "S0#M1.B0.P2") to its content. Refs use short labels (S0, S1, ...) instead of full session IDs for token efficiency. Format: S{n}#M{msg}[.B{block}[.P{para}]]',
    inputSchema: {
      type: 'object',
      properties: {
        ref: { type: 'string', description: 'Compact session ref, e.g. "S0#M1.B0.P2"' },
      },
      required: ['ref'],
    },
  },
  {
    name: 'index_search',
    description: 'Full-text search across indexed session message history. Returns matching fragments with compact refs.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search query' },
        label: { type: 'string', description: 'Short session label (e.g. "S0") to restrict search' },
        sessionId: { type: 'string', description: 'Full session ID to restrict search (alternative to label)' },
        limit: { type: 'number', description: 'Max results (default 20)' },
      },
      required: ['query'],
    },
  },
  {
    name: 'index_session',
    description: "Index a session's full message history for granular referencing. Returns the assigned short label. Use POST /memory/index/:sessionId on the admin API.",
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'Session ID to index' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'index_stats',
    description: 'Get index stats for a session (message count, block count, paragraph count). Accepts either a short label or full session ID.',
    inputSchema: {
      type: 'object',
      properties: {
        labelOrSessionId: { type: 'string', description: 'Short label (e.g. "S0") or full session ID' },
      },
      required: ['labelOrSessionId'],
    },
  },
];

/**
 * Session tool names set for quick lookup
 */
export const SESSION_TOOL_NAMES = new Set(SESSION_TOOLS.map(t => t.name));

/**
 * Execute a session tool
 */
export async function executeSessionTool(
  baseUrl: string,
  toolName: string,
  args: any,
  logger: ILogger
): Promise<any> {
  logger.info('Executing session tool', { tool: toolName, args });

  switch (toolName) {
    case 'sessions': {
      const params = new URLSearchParams();
      if (args?.limit) params.set('limit', String(args.limit));
      const qs = params.toString();
      const res = await fetchWithTimeout(`${baseUrl}/sessions${qs ? '?' + qs : ''}`);
      if (!res.ok) throw new Error(`Sessions list failed: ${await res.text()}`);
      return await res.json();
    }

    case 'session_detail': {
      const sid = encodeURIComponent(args.sessionId);
      const sessionRes = await fetchWithTimeout(`${baseUrl}/sessions/${sid}`);
      if (!sessionRes.ok) throw new Error(`Session detail failed: ${await sessionRes.text()}`);
      const session = await sessionRes.json();

      if (args.includeMessages) {
        const params = new URLSearchParams();
        if (args.messageLimit) params.set('limit', String(args.messageLimit));
        const qs = params.toString();
        const msgRes = await fetchWithTimeout(`${baseUrl}/sessions/${sid}/messages${qs ? '?' + qs : ''}`);
        if (msgRes.ok) {
          session.messages = await msgRes.json();
        }
      }
      return session;
    }

    case 'session_prune': {
      const res = await fetchWithTimeout(`${baseUrl}/sessions/prune`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(args || {}),
      });
      if (!res.ok) throw new Error(`Session prune failed: ${await res.text()}`);
      return await res.json();
    }

    case 'session_conversation': {
      const params = new URLSearchParams();
      if (args.limit) params.set('limit', String(args.limit));
      const qs = params.toString();
      const res = await fetchWithTimeout(`${baseUrl}/memory/session/${encodeURIComponent(args.sessionId)}/conversation${qs ? '?' + qs : ''}`);
      if (!res.ok) throw new Error(`Session conversation failed: ${await res.text()}`);
      return await res.json();
    }

    case 'session_export': {
      const res = await fetchWithTimeout(`${baseUrl}/memory/session/${encodeURIComponent(args.sessionId)}/export`);
      if (!res.ok) throw new Error(`Session export failed: ${await res.text()}`);
      return await res.json();
    }

    case 'resolve_ref': {
      const res = await fetchWithTimeout(`${baseUrl}/memory/ref/${encodeURIComponent(args.ref)}`);
      if (!res.ok) throw new Error(`Ref resolution failed: ${await res.text()}`);
      return await res.json();
    }

    case 'index_search': {
      const params = new URLSearchParams();
      params.set('q', args.query);
      if (args.limit) params.set('limit', String(args.limit));
      const labelOrId = args.label || args.sessionId || '';
      if (!labelOrId) throw new Error('label or sessionId is required');
      const res = await fetchWithTimeout(`${baseUrl}/memory/index/${encodeURIComponent(labelOrId)}/search?${params}`);
      if (!res.ok) throw new Error(`Index search failed: ${await res.text()}`);
      return await res.json();
    }

    case 'index_session': {
      const res = await fetchWithTimeout(`${baseUrl}/memory/index/${encodeURIComponent(args.sessionId)}`, { method: 'POST' });
      if (!res.ok) throw new Error(`Session indexing failed: ${await res.text()}`);
      return await res.json();
    }

    case 'index_stats': {
      const res = await fetchWithTimeout(`${baseUrl}/memory/index/${encodeURIComponent(args.labelOrSessionId)}/stats`);
      if (!res.ok) throw new Error(`Index stats failed: ${await res.text()}`);
      return await res.json();
    }

    default:
      throw new Error(`Unknown session tool: ${toolName}`);
  }
}

/**
 * Get all session tool definitions
 */
export function getSessionTools(): Array<{
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}> {
  return SESSION_TOOLS;
}
