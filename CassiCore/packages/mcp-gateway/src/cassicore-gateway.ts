#!/usr/bin/env node
/**
 * CassiCore MCP Gateway Server
 * 
 * Exposes CassiCore's tools and capabilities via the Model Context Protocol (MCP).
 * This allows external AI systems (like Qwen-Coder) to use CassiCore's tool ecosystem.
 * 
 * Supports:
 * - stdio transport (for direct IDE integration)
 * - HTTP/SSE transport (for remote connections)
 * 
 * Usage:
 *   node mcp/cassicore-gateway.ts                    # stdio mode (default)
 *   node mcp/cassicore-gateway.ts --http --port 3000 # HTTP mode
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import http from 'http';
import { spawn } from 'child_process';

// Configuration
const CASSICORE_URL = process.env.CASSICORE_URL || 'http://localhost:7433';
const GATEWAY_VERSION = '1.0.0';
const DEFAULT_FETCH_TIMEOUT_MS = 30_000; // 30s default timeout for all fetch calls

// Logger that writes to stderr (stdout reserved for MCP protocol)
function log(level: string, message: string, data?: any) {
  const timestamp = new Date().toISOString();
  const logLine = JSON.stringify({ timestamp, level, message, data });
  console.error(logLine);
}

/**
 * Fetch with timeout — wraps global fetch with AbortController to prevent
 * indefinite hangs when the daemon is slow or unresponsive.
 */
async function fetchWithTimeout(url: string | URL, init?: RequestInit & { timeoutMs?: number }): Promise<Response> {
  const timeoutMs = init?.timeoutMs ?? DEFAULT_FETCH_TIMEOUT_MS;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url.toString(), {
      ...init,
      signal: controller.signal,
    });
  } catch (err: any) {
    if (err?.name === 'AbortError') {
      throw new Error(`Request to ${url} timed out after ${timeoutMs}ms`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Tool definitions - mirror of CassiCore's tool registry
 */
const CASSICORE_TOOLS = [
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
 * Intelligence Activity Viewer tools — expose CassiCore's cognitive state
 */
const INTELLIGENCE_TOOLS = [
  {
    name: 'cassi_activity',
    description: 'Dashboard of all CassiCore cognitive modules — status, recent activity, injection counts, session health. Use this for a high-level overview of what the intelligence layer is doing.',
    inputSchema: {
      type: 'object',
      properties: {
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for a short narrative summary (default), "full" for a detailed dashboard with tables',
        },
      },
    },
  },
  {
    name: 'cassi_dialectic',
    description: 'View the Yang/Yin/Synthesizer dialectic analysis — recent turns, signal injection history, confidence scores, and synthesis outcomes. Shows how the dialectic trio processes each conversation turn.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: {
          type: 'string',
          description: 'Session ID to inspect (optional, defaults to most recent active session)',
        },
        limit: {
          type: 'number',
          description: 'Number of recent dialectic turns to show (default 5)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed dashboard',
        },
      },
    },
  },
  {
    name: 'cassi_thinker',
    description: 'View the Thinker module state — adaptive strategy parameters, insight history, ponder/think stats, Phase 3 trigger activity, and self-modification events.',
    inputSchema: {
      type: 'object',
      properties: {
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed dashboard',
        },
      },
    },
  },
  {
    name: 'cassi_subconscious',
    description: 'Conscious Observer state — system-wide mental model (session tracking, provider health, plugin status, active drones/teams, budget tiers), observations from heuristic and LLM sweeps, and detected anomalies. Use this to understand the overall health and awareness state of the intelligence layer.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: {
          type: 'string',
          description: 'Session ID to inspect (optional, defaults to most recent active session)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed dashboard',
        },
      },
    },
  },
  {
    name: 'cassi_consciousness',
    description: 'Real-time event stream and observer pipeline — what\'s flowing through the system right now. Shows event rate, top event types, recent event sequence, heuristic vs LLM observation counts, and last LLM sweep timing. Use this to understand the live pulse of the intelligence layer.',
    inputSchema: {
      type: 'object',
      properties: {
        windowSecs: {
          type: 'number',
          description: 'Look-back window in seconds for stream stats (default 60)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for key metrics (default), "full" for full event type breakdown and LLM observation history',
        },
      },
    },
  },
  {
    name: 'cassi_trace',
    description: 'Forensic trace of a conversation turn — reconstructs what cognitive influences (optimizer, thinker, dialectic, subconscious, session digest) shaped a specific response. Use when asking "why did Cassi say that?"',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: {
          type: 'string',
          description: 'Session ID to trace (optional, defaults to most recent active session)',
        },
        turnIndex: {
          type: 'number',
          description: 'Specific turn index to focus on (optional, shows most recent turns if omitted)',
        },
        limit: {
          type: 'number',
          description: 'Number of turns to include in context (default 5)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed forensic data',
        },
      },
    },
  },
  {
    name: 'cassi_effectiveness',
    description: 'Response quality metrics from implicit feedback signals — "Am I helping?" Shows outcome tracking, feedback detection, per-source quality scores, and per-tool reliability.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: {
          type: 'string',
          description: 'Session ID for feedback lookup (optional, defaults to most recent active session)',
        },
        windowHours: {
          type: 'number',
          description: 'Time window in hours for source/tool stats (default 24)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed metrics',
        },
      },
    },
  },
  {
    name: 'cassi_budget',
    description: 'Token economy and provider usage — "Where does my attention go?" Shows request counts, error rates, per-provider/model aggregates, and hourly trends. No dollar cost calculation.',
    inputSchema: {
      type: 'object',
      properties: {
        providerId: {
          type: 'string',
          description: 'Filter by provider ID (e.g., "anthropic", "github-copilot")',
        },
        model: {
          type: 'string',
          description: 'Filter by model name',
        },
        hours: {
          type: 'number',
          description: 'Hours of hourly trend data to include (default 24)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed dashboard',
        },
      },
    },
  },
  {
    name: 'cassi_evolution',
    description: 'Self-modification timeline — "Am I changing?" Shows strategy snapshots over time, best strategies per module, dialectic effectiveness scores, and parameter evolution.',
    inputSchema: {
      type: 'object',
      properties: {
        module: {
          type: 'string',
          description: 'Intelligence module name to focus on (e.g., "thinker", "dialectic", "optimizer")',
        },
        limit: {
          type: 'number',
          description: 'Number of history entries to show (default 10)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed timeline',
        },
      },
    },
  },
  {
    name: 'cassi_blindspots',
    description: 'Cross-session pattern detection — "What am I systematically missing?" Shows recurring patterns across sessions, error correlations, and unresolved reflection patterns.',
    inputSchema: {
      type: 'object',
      properties: {
        category: {
          type: 'string',
          description: 'Filter patterns by category',
        },
        minConfidence: {
          type: 'number',
          description: 'Minimum confidence threshold (0-1, default 0)',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of patterns to return (default 10)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed patterns',
        },
      },
    },
  },
  {
    name: 'cassi_snapshot',
    description: 'Get a comprehensive snapshot of all running team agents, their goals, progress, recent messages, and current git status. Use this to monitor ongoing parallel work.',
    inputSchema: {
      type: 'object' as const,
      properties: {
        teamId: {
          type: 'string',
          description: 'Optional: focus on a specific team. If omitted, shows all running teams.'
        },
        includeMessages: {
          type: 'boolean',
          description: 'Whether to include recent agent messages (default: true)'
        },
        messageLimit: {
          type: 'number',
          description: 'Max recent messages per agent (default: 5)'
        }
      }
    }
  },
];
// ═══════════════════════════════════════════════════════════════════════════════
// Extended Tools — Memory, Providers, Config, Sessions, Actions, Teams
// ═══════════════════════════════════════════════════════════════════════════════

const MEMORY_TOOLS = [
  {
    name: 'cassi_memory_store',
    description: 'Store a memory in CassiCore\'s persistent memory system. Memories persist across sessions and can be searched later.',
    inputSchema: {
      type: 'object',
      properties: {
        key: {
          type: 'string',
          description: 'A unique key/identifier for this memory',
        },
        content: {
          type: 'string',
          description: 'The content to store',
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: 'Optional tags for categorization',
        },
      },
      required: ['key', 'content'],
    },
  },
  {
    name: 'cassi_memory_search',
    description: 'Search CassiCore\'s persistent memory using full-text search. Returns matching memories with relevance scores.',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query (supports FTS5 syntax)',
        },
        limit: {
          type: 'number',
          description: 'Maximum results to return (default 10)',
        },
      },
      required: ['query'],
    },
  },
  {
    name: 'cassi_memory_recent',
    description: 'List the most recently stored memories.',
    inputSchema: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Maximum results to return (default 10)',
        },
      },
    },
  },
  {
    name: 'cassi_memory_delete',
    description: 'Delete a memory entry by its ID.',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: 'Memory entry ID to delete' },
      },
      required: ['id'],
    },
  },
  {
    name: 'cassi_memory_kv_get',
    description: 'Retrieve a value from the persistent key-value store.',
    inputSchema: {
      type: 'object',
      properties: {
        key: { type: 'string', description: 'KV store key' },
      },
      required: ['key'],
    },
  },
  {
    name: 'cassi_memory_kv_set',
    description: 'Store a value in the persistent key-value store. Survives daemon restarts.',
    inputSchema: {
      type: 'object',
      properties: {
        key: { type: 'string', description: 'KV store key' },
        value: { description: 'Value to store (any JSON-serializable type)' },
      },
      required: ['key', 'value'],
    },
  },
  {
    name: 'cassi_memory_kv_del',
    description: 'Delete a key from the persistent key-value store.',
    inputSchema: {
      type: 'object',
      properties: {
        key: { type: 'string', description: 'KV store key to delete' },
      },
      required: ['key'],
    },
  },
  {
    name: 'cassi_memory_stats',
    description: 'Get memory system statistics — entry counts by type, archive stats, and queue depth.',
    inputSchema: { type: 'object', properties: {} },
  },
  {
    name: 'cassi_archive_search',
    description: 'Search the archive (conversations, insights, patterns, dialectic outputs, events) with rich filtering.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Full-text search query' },
        limit: { type: 'number', description: 'Max results (default 20)' },
        sortBy: { type: 'string', enum: ['relevance', 'importance', 'time'], description: 'Sort order (default relevance)' },
        filters: {
          type: 'object',
          description: 'Optional filters',
          properties: {
            types: { type: 'array', items: { type: 'string' }, description: 'e.g. ["conversation","insight","pattern"]' },
            sessionId: { type: 'string' },
            minImportance: { type: 'number' },
            maxImportance: { type: 'number' },
            sentiment: { type: 'string' },
            topics: { type: 'array', items: { type: 'string' } },
            entities: { type: 'array', items: { type: 'string' } },
            tags: { type: 'array', items: { type: 'string' } },
            hasThinking: { type: 'boolean' },
            startTime: { type: 'number', description: 'Unix seconds' },
            endTime: { type: 'number', description: 'Unix seconds' },
            source: { type: 'string' },
          },
        },
      },
      required: ['query'],
    },
  },
  {
    name: 'cassi_archive_get',
    description: 'Get a single archive entry by ID.',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: 'Archive entry ID' },
      },
      required: ['id'],
    },
  },
  {
    name: 'cassi_archive_related',
    description: 'Find archive entries related to a given entry (by entity/topic overlap).',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: 'Archive entry ID to find related entries for' },
        limit: { type: 'number', description: 'Max results (default 10)' },
      },
      required: ['id'],
    },
  },
  {
    name: 'cassi_archive_recent',
    description: 'List the most recently archived entries across all types (conversations, insights, patterns, etc.).',
    inputSchema: {
      type: 'object',
      properties: {
        limit: { type: 'number', description: 'Max results (default 10)' },
      },
    },
  },
  {
    name: 'cassi_browse',
    description: 'Browse the archive index — list all tags, entities, or topics with their occurrence counts.',
    inputSchema: {
      type: 'object',
      properties: {
        category: {
          type: 'string',
          enum: ['tags', 'entities', 'topics'],
          description: 'What to browse',
        },
        minCount: { type: 'number', description: 'Minimum occurrence count to include (default 1)' },
      },
      required: ['category'],
    },
  },
  {
    name: 'cassi_universal_search',
    description: 'Search across both the memory store and the archive in one call.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search query' },
        includeMemories: { type: 'boolean', description: 'Include memory store results (default true)' },
        includeArchives: { type: 'boolean', description: 'Include archive results (default true)' },
        limit: { type: 'number', description: 'Max results per source (default 10)' },
      },
      required: ['query'],
    },
  },
  {
    name: 'cassi_session_conversation',
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
    name: 'cassi_session_export',
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
    name: 'cassi_resolve_ref',
    description: 'Resolve a compact session ref (e.g. "S0#M1.B0.P2") to its content. Refs use short labels (S0, S1, …) instead of full session IDs for token efficiency. Format: S{n}#M{msg}[.B{block}[.P{para}]]',
    inputSchema: {
      type: 'object',
      properties: {
        ref: { type: 'string', description: 'Compact session ref, e.g. "S0#M1.B0.P2"' },
      },
      required: ['ref'],
    },
  },
  {
    name: 'cassi_index_search',
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
    name: 'cassi_index_session',
    description: 'Index a session\'s full message history for granular referencing. Returns the assigned short label. Use POST /memory/index/:sessionId on the admin API.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'Session ID to index' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'cassi_index_stats',
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

const PROVIDER_TOOLS = [
  {
    name: 'cassi_providers',
    description: 'List all configured LLM providers with their health status, available models, and quota information.',
    inputSchema: {
      type: 'object',
      properties: {
        includeHealth: {
          type: 'boolean',
          description: 'Include detailed health and quota data (default true)',
        },
      },
    },
  },
  {
    name: 'cassi_provider_metrics',
    description: 'Get aggregated provider performance metrics — request counts, latency, error rates, token usage per provider/model.',
    inputSchema: {
      type: 'object',
      properties: {
        providerId: {
          type: 'string',
          description: 'Filter by provider ID (e.g., "anthropic", "github-copilot")',
        },
        model: {
          type: 'string',
          description: 'Filter by model name',
        },
      },
    },
  },
  {
    name: 'cassi_provider_config',
    description: 'View or modify provider configuration. Use action "get" to read current config, "set" to update, "reset" to clear error state.',
    inputSchema: {
      type: 'object',
      properties: {
        action: {
          type: 'string',
          enum: ['get', 'set', 'reset'],
          description: 'Action to perform (default "get")',
        },
        providerId: {
          type: 'string',
          description: 'Provider ID (required for "set" and "reset")',
        },
        config: {
          type: 'object',
          description: 'Configuration object to set (for action "set")',
        },
      },
    },
  },
];

const CONFIG_TOOLS = [
  {
    name: 'cassi_config_get',
    description: 'Read CassiCore runtime configuration. Optionally specify a key to read a single value, or omit for the full config.',
    inputSchema: {
      type: 'object',
      properties: {
        key: {
          type: 'string',
          description: 'Specific config key path (e.g., "intelligence.thinker.enabled"). Omit for full config.',
        },
      },
    },
  },
  {
    name: 'cassi_config_set',
    description: 'Modify CassiCore runtime configuration (hot-reloaded). Restricted to safe keys: intelligence.*, providers.*.model, providers.*.enabled, channels.*.enabled, logging.level.',
    inputSchema: {
      type: 'object',
      properties: {
        key: {
          type: 'string',
          description: 'Config key path to set',
        },
        value: {
          description: 'Value to set (string, number, boolean, or object)',
        },
      },
      required: ['key', 'value'],
    },
  },
];

const SESSION_TOOLS = [
  {
    name: 'cassi_sessions',
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
    name: 'cassi_session_detail',
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
    name: 'cassi_session_prune',
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
];

const ACTION_TOOLS = [
  {
    name: 'cassi_think_now',
    description: 'Trigger a manual Thinker cycle immediately. Returns the generated insight.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: {
          type: 'string',
          description: 'Session context for the think cycle (optional, uses most recent)',
        },
        prompt: {
          type: 'string',
          description: 'Optional prompt to focus the thinking on a specific topic',
        },
      },
    },
  },
  {
    name: 'cassi_strategy_update',
    description: 'View or modify the Thinker\'s adaptive strategy parameters (ponder interval, trigger sensitivity, etc.).',
    inputSchema: {
      type: 'object',
      properties: {
        action: {
          type: 'string',
          enum: ['get', 'set', 'reset'],
          description: 'Action: "get" to read current strategy, "set" to modify, "reset" to restore defaults',
        },
        strategy: {
          type: 'object',
          description: 'Strategy parameters to set (for action "set"). Partial updates supported.',
        },
      },
    },
  },
  {
    name: 'cassi_anomaly_ack',
    description: 'Acknowledge a subconscious anomaly to dismiss it from active monitoring.',
    inputSchema: {
      type: 'object',
      properties: {
        anomalyId: {
          type: 'string',
          description: 'The anomaly ID to acknowledge',
        },
      },
      required: ['anomalyId'],
    },
  },
];

const TEAM_TOOLS = [
  {
    name: 'cassi_team',
    description: 'Multi-agent team orchestration — start, monitor, and control autonomous agent teams. Use the "action" parameter to select the operation.',
    inputSchema: {
      type: 'object',
      properties: {
        action: {
          type: 'string',
          enum: ['start', 'status', 'tree', 'list', 'pause', 'resume', 'cancel', 'checkpoints', 'approve', 'reject', 'steer'],
          description: 'Team operation to perform',
        },
        goal: {
          type: 'string',
          description: 'Goal description (for action "start")',
        },
        roles: {
          type: 'array',
          items: { type: 'string' },
          description: 'Agent roles to assign (for action "start")',
        },
        teamId: {
          type: 'string',
          description: 'Team ID (required for status/tree/pause/resume/cancel/steer)',
        },
        checkpointId: {
          type: 'string',
          description: 'Checkpoint ID (required for approve/reject)',
        },
        feedback: {
          type: 'string',
          description: 'Feedback or steering instructions (for approve/reject/steer)',
        },
        budget: {
          type: 'object',
          description: 'Resource budget constraints (for action "start")',
          properties: {
            maxTokens: { type: 'number' },
            maxIterations: { type: 'number' },
            timeoutMs: { type: 'number' },
          },
        },
      },
      required: ['action'],
    },
  },
];

// ── C3: Agent-level team coordination tools ──────────────────────────────────
// These tools are designed for agents running inside a team context (Phase 3 Hybrid Executor).
// They expose the same capabilities as the 8 internal team-coordinator tools but via MCP.
const TEAM_AGENT_TOOLS = [
  {
    name: 'cassi_team_agent_status',
    description: 'Get the current status of the team including goal tree, progress, active agents, and budget usage. Use this to understand what has been accomplished and what remains.',
    inputSchema: {
      type: 'object',
      properties: {
        teamId: { type: 'string', description: 'The team ID to check status for' },
      },
      required: ['teamId'],
    },
  },
  {
    name: 'cassi_team_agent_message',
    description: 'Send a message to another agent in the team via the mailbox system. Use for coordination, sharing intermediate results, or requesting help.',
    inputSchema: {
      type: 'object',
      properties: {
        toAgentId: { type: 'string', description: 'ID of the agent to send the message to' },
        message: { type: 'string', description: 'The message content' },
        agentId: { type: 'string', description: 'Your agent ID (sender)' },
      },
      required: ['toAgentId', 'message'],
    },
  },
  {
    name: 'cassi_team_agent_result',
    description: 'Get the result from a completed agent. Use to retrieve another agent\'s output after they finish their task.',
    inputSchema: {
      type: 'object',
      properties: {
        agentId: { type: 'string', description: 'ID of the agent whose result to retrieve' },
      },
      required: ['agentId'],
    },
  },
  {
    name: 'cassi_team_agent_list',
    description: 'List all agents in a team with their goals, status, and roles.',
    inputSchema: {
      type: 'object',
      properties: {
        teamId: { type: 'string', description: 'The team ID to list agents for' },
      },
      required: ['teamId'],
    },
  },
  {
    name: 'cassi_team_agent_update_plan',
    description: 'Update the team plan by adding new sub-goals or modifying existing ones. Use when you need to break down work further or adjust the plan.',
    inputSchema: {
      type: 'object',
      properties: {
        teamId: { type: 'string', description: 'The team ID' },
        addGoals: {
          type: 'array',
          description: 'New sub-goals to add',
          items: {
            type: 'object',
            properties: {
              title: { type: 'string' },
              description: { type: 'string' },
              parentGoalId: { type: 'string' },
              roleHint: { type: 'string' },
            },
            required: ['title', 'parentGoalId'],
          },
        },
        updateGoals: {
          type: 'array',
          description: 'Existing goals to update',
          items: {
            type: 'object',
            properties: {
              goalId: { type: 'string' },
              status: { type: 'string', enum: ['pending', 'in_progress', 'completed', 'failed', 'blocked'] },
            },
            required: ['goalId'],
          },
        },
      },
      required: ['teamId'],
    },
  },
  {
    name: 'cassi_team_agent_complete_goal',
    description: 'Signal completion (or failure) of a team goal. Call this when you have finished working on your assigned goal.',
    inputSchema: {
      type: 'object',
      properties: {
        teamId: { type: 'string', description: 'The team ID' },
        goalId: { type: 'string', description: 'The goal ID being completed' },
        summary: { type: 'string', description: 'Summary of what was accomplished' },
        result: { type: 'string', description: 'Detailed result output' },
        success: { type: 'boolean', description: 'Whether the goal succeeded (default: true)' },
        error: { type: 'string', description: 'Error message if failed' },
      },
      required: ['teamId', 'goalId', 'summary'],
    },
  },
  {
    name: 'cassi_team_agent_goal_tree',
    description: 'Get the full goal tree for a team, showing all goals, their hierarchy, statuses, and progress.',
    inputSchema: {
      type: 'object',
      properties: {
        teamId: { type: 'string', description: 'The team ID' },
      },
      required: ['teamId'],
    },
  },
];

/**
 * Execute an agent-level team coordination tool via CassiCore admin API (C3)
 */
async function executeTeamAgentTool(toolName: string, args: any): Promise<any> {
  log('info', 'Executing team agent tool', { tool: toolName, args });

  try {
    switch (toolName) {
      case 'cassi_team_agent_status': {
        if (!args.teamId) throw new Error('teamId is required');
        const res = await fetchWithTimeout(`${CASSICORE_URL}/teams/status?teamId=${encodeURIComponent(args.teamId)}`);
        if (!res.ok) throw new Error(`Team status failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_team_agent_message': {
        const res = await fetchWithTimeout(`${CASSICORE_URL}/teams/agent/message`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            toAgentId: args.toAgentId,
            message: args.message,
            agentId: args.agentId,
          }),
        });
        if (!res.ok) throw new Error(`Send message failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_team_agent_result': {
        if (!args.agentId) throw new Error('agentId is required');
        const res = await fetchWithTimeout(`${CASSICORE_URL}/teams/agent/result?agentId=${encodeURIComponent(args.agentId)}`);
        if (!res.ok) throw new Error(`Get agent result failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_team_agent_list': {
        if (!args.teamId) throw new Error('teamId is required');
        const res = await fetchWithTimeout(`${CASSICORE_URL}/teams/agent/list?teamId=${encodeURIComponent(args.teamId)}`);
        if (!res.ok) throw new Error(`List agents failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_team_agent_update_plan': {
        const res = await fetchWithTimeout(`${CASSICORE_URL}/teams/agent/update-plan`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            teamId: args.teamId,
            addGoals: args.addGoals,
            updateGoals: args.updateGoals,
          }),
        });
        if (!res.ok) throw new Error(`Update plan failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_team_agent_complete_goal': {
        const res = await fetchWithTimeout(`${CASSICORE_URL}/teams/agent/complete-goal`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            teamId: args.teamId,
            goalId: args.goalId,
            summary: args.summary,
            result: args.result,
            success: args.success,
            error: args.error,
          }),
        });
        if (!res.ok) throw new Error(`Complete goal failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_team_agent_goal_tree': {
        if (!args.teamId) throw new Error('teamId is required');
        const res = await fetchWithTimeout(`${CASSICORE_URL}/teams/agent/goal-tree?teamId=${encodeURIComponent(args.teamId)}`);
        if (!res.ok) throw new Error(`Get goal tree failed: ${await res.text()}`);
        return await res.json();
      }

      default:
        throw new Error(`Unknown team agent tool: "${toolName}"`);
    }
  } catch (error: any) {
    log('error', 'Team agent tool execution failed', { tool: toolName, error: error.message });
    throw error;
  }
}
async function executeCassiCoreTool(toolName: string, args: any): Promise<any> {
  log('info', 'Executing CassiCore tool', { tool: toolName, args });

  // Map tool names to CassiCore API endpoints
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

  const endpoint = endpointMap[toolName];
  if (!endpoint) {
    throw new Error(`Unknown tool: ${toolName}`);
  }

  const url = `${CASSICORE_URL}${endpoint}`;
  
  // Determine HTTP method based on tool
  const readTools = ['read', 'exists'];
  const method = readTools.includes(toolName) ? 'GET' : 'POST';

  try {
    let response;
    
    if (method === 'GET') {
      const queryParams = new URLSearchParams(args).toString();
      response = await fetchWithTimeout(`${url}?${queryParams}`, {
        method: 'GET',
        timeoutMs: toolName === 'bash' ? 120_000 : DEFAULT_FETCH_TIMEOUT_MS, // bash gets longer timeout
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

    // Safely parse JSON — handle non-JSON responses from error pages or proxy
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('json')) {
      return await response.json();
    }
    const text = await response.text();
    return { output: text };
  } catch (error: any) {
    log('error', 'Tool execution failed', { tool: toolName, error: error.message });
    throw error;
  }
}



// ═══════════════════════════════════════════════════════════════════════════════
// Extended Tool Execution (Memory, Providers, Config, Sessions, Actions, Teams)
// ═══════════════════════════════════════════════════════════════════════════════

/** Safe config keys that can be modified via cassi_config_set */
const SAFE_CONFIG_KEYS = [
  'intelligence.',
  'providers.*.model',
  'providers.*.enabled',
  'channels.*.enabled',
  'logging.level',
];

function isConfigKeySafe(key: string): boolean {
  return SAFE_CONFIG_KEYS.some(pattern => {
    if (pattern.endsWith('.')) return key.startsWith(pattern);
    // Convert wildcard pattern to regex
    const regex = new RegExp('^' + pattern.replace(/\./g, '\\.').replace(/\*/g, '[^.]+') + '$');
    return regex.test(key);
  });
}

/**
 * Execute extended tools (memory, providers, config, sessions, actions, teams)
 * via CassiCore admin API using the JSON proxy pattern.
 */
async function executeExtendedTool(toolName: string, args: any): Promise<any> {
  log('info', 'Executing extended tool', { tool: toolName, args });

  try {
    switch (toolName) {
      // ── Memory ──────────────────────────────────────────────────────────
      case 'cassi_memory_store': {
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/store`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key: args.key, content: args.content, tags: args.tags }),
        });
        if (!res.ok) throw new Error(`Memory store failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_memory_search': {
        const params = new URLSearchParams({ query: args.query });
        if (args.limit) params.set('limit', String(args.limit));
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/search?${params}`);
        if (!res.ok) throw new Error(`Memory search failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_memory_recent': {
        const params = new URLSearchParams();
        if (args?.limit) params.set('limit', String(args.limit));
        const qs = params.toString();
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/recent${qs ? '?' + qs : ''}`);
        if (!res.ok) throw new Error(`Memory recent failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_memory_delete': {
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/${encodeURIComponent(args.id)}`, { method: 'DELETE' });
        if (!res.ok) throw new Error(`Memory delete failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_memory_kv_get': {
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/kv/${encodeURIComponent(args.key)}`);
        if (!res.ok) throw new Error(`KV get failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_memory_kv_set': {
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/kv`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key: args.key, value: args.value }),
        });
        if (!res.ok) throw new Error(`KV set failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_memory_kv_del': {
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/kv/${encodeURIComponent(args.key)}`, { method: 'DELETE' });
        if (!res.ok) throw new Error(`KV delete failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_memory_stats': {
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/stats`);
        if (!res.ok) throw new Error(`Memory stats failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_archive_search': {
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/archives/search`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: args.query, limit: args.limit, sortBy: args.sortBy, filters: args.filters }),
        });
        if (!res.ok) throw new Error(`Archive search failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_archive_get': {
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/archives/${encodeURIComponent(args.id)}`);
        if (!res.ok) throw new Error(`Archive get failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_archive_related': {
        const params = new URLSearchParams();
        if (args.limit) params.set('limit', String(args.limit));
        const qs = params.toString();
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/archives/${encodeURIComponent(args.id)}/related${qs ? '?' + qs : ''}`);
        if (!res.ok) throw new Error(`Archive related failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_archive_recent': {
        const params = new URLSearchParams();
        if (args?.limit) params.set('limit', String(args.limit));
        const qs = params.toString();
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/archives/recent${qs ? '?' + qs : ''}`);
        if (!res.ok) throw new Error(`Archive recent failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_browse': {
        const params = new URLSearchParams({ category: args.category });
        if (args.minCount) params.set('minCount', String(args.minCount));
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/archives/browse?${params}`);
        if (!res.ok) throw new Error(`Browse failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_universal_search': {
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/universal-search`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: args.query, includeMemories: args.includeMemories, includeArchives: args.includeArchives, limit: args.limit }),
        });
        if (!res.ok) throw new Error(`Universal search failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_session_conversation': {
        const params = new URLSearchParams();
        if (args.limit) params.set('limit', String(args.limit));
        const qs = params.toString();
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/session/${encodeURIComponent(args.sessionId)}/conversation${qs ? '?' + qs : ''}`);
        if (!res.ok) throw new Error(`Session conversation failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_session_export': {
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/session/${encodeURIComponent(args.sessionId)}/export`);
        if (!res.ok) throw new Error(`Session export failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_resolve_ref': {
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/ref/${encodeURIComponent(args.ref)}`);
        if (!res.ok) throw new Error(`Ref resolution failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_index_search': {
        const params = new URLSearchParams();
        params.set('q', args.query);
        if (args.limit) params.set('limit', String(args.limit));
        const labelOrId = args.label || args.sessionId || '';
        if (!labelOrId) throw new Error('label or sessionId is required');
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/index/${encodeURIComponent(labelOrId)}/search?${params}`);
        if (!res.ok) throw new Error(`Index search failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_index_session': {
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/index/${encodeURIComponent(args.sessionId)}`, { method: 'POST' });
        if (!res.ok) throw new Error(`Session indexing failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_index_stats': {
        const res = await fetchWithTimeout(`${CASSICORE_URL}/memory/index/${encodeURIComponent(args.labelOrSessionId)}/stats`);
        if (!res.ok) throw new Error(`Index stats failed: ${await res.text()}`);
        return await res.json();
      }

      // ── Providers ───────────────────────────────────────────────────────
      case 'cassi_providers': {
        const providersRes = await fetchWithTimeout(`${CASSICORE_URL}/providers`);
        if (!providersRes.ok) throw new Error(`Providers list failed: ${await providersRes.text().catch(() => 'unknown')}`);
        const providers = await providersRes.json();
        // Health endpoint is best-effort — don't fail the whole call if it 404s
        let health = null;
        if (args?.includeHealth !== false) {
          try {
            const healthRes = await fetchWithTimeout(`${CASSICORE_URL}/health/providers`);
            if (healthRes.ok) health = await healthRes.json();
          } catch { /* best-effort */ }
        }
        return health ? { providers, health } : providers;
      }

      case 'cassi_provider_metrics': {
        const params = new URLSearchParams();
        if (args?.providerId) params.set('providerId', args.providerId);
        if (args?.model) params.set('model', args.model);
        const qs = params.toString();
        const res = await fetchWithTimeout(`${CASSICORE_URL}/providers/metrics${qs ? '?' + qs : ''}`);
        if (!res.ok) throw new Error(`Provider metrics failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_provider_config': {
        const action = args?.action || 'get';
        if (action === 'get') {
          const res = await fetchWithTimeout(`${CASSICORE_URL}/providers/config`);
          if (!res.ok) throw new Error(`Provider config get failed: ${await res.text()}`);
          return await res.json();
        } else if (action === 'set') {
          const res = await fetchWithTimeout(`${CASSICORE_URL}/providers/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ providerId: args.providerId, config: args.config }),
          });
          if (!res.ok) throw new Error(`Provider config set failed: ${await res.text()}`);
          return await res.json();
        } else if (action === 'reset') {
          const res = await fetchWithTimeout(`${CASSICORE_URL}/providers/reset`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ providerId: args.providerId }),
          });
          if (!res.ok) throw new Error(`Provider reset failed: ${await res.text()}`);
          return await res.json();
        }
        throw new Error(`Unknown provider config action: ${action}`);
      }

      // ── Config ──────────────────────────────────────────────────────────
      case 'cassi_config_get': {
        const path = args?.key ? `/config/${encodeURIComponent(args.key)}` : '/config';
        const res = await fetchWithTimeout(`${CASSICORE_URL}${path}`);
        if (!res.ok) throw new Error(`Config get failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_config_set': {
        if (!isConfigKeySafe(args.key)) {
          throw new Error(
            `Config key "${args.key}" is not in the safe-list. ` +
            `Allowed patterns: ${SAFE_CONFIG_KEYS.join(', ')}`
          );
        }
        const res = await fetchWithTimeout(`${CASSICORE_URL}/config/set`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key: args.key, value: args.value }),
        });
        if (!res.ok) throw new Error(`Config set failed: ${await res.text()}`);
        return await res.json();
      }

      // ── Sessions ────────────────────────────────────────────────────────
      case 'cassi_sessions': {
        const params = new URLSearchParams();
        if (args?.limit) params.set('limit', String(args.limit));
        const qs = params.toString();
        const res = await fetchWithTimeout(`${CASSICORE_URL}/sessions${qs ? '?' + qs : ''}`);
        if (!res.ok) throw new Error(`Sessions list failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_session_detail': {
        const sid = encodeURIComponent(args.sessionId);
        const sessionRes = await fetchWithTimeout(`${CASSICORE_URL}/sessions/${sid}`);
        if (!sessionRes.ok) throw new Error(`Session detail failed: ${await sessionRes.text()}`);
        const session = await sessionRes.json();

        if (args.includeMessages) {
          const params = new URLSearchParams();
          if (args.messageLimit) params.set('limit', String(args.messageLimit));
          const qs = params.toString();
          const msgRes = await fetchWithTimeout(`${CASSICORE_URL}/sessions/${sid}/messages${qs ? '?' + qs : ''}`);
          if (msgRes.ok) {
            session.messages = await msgRes.json();
          }
        }
        return session;
      }

      case 'cassi_session_prune': {
        const res = await fetchWithTimeout(`${CASSICORE_URL}/sessions/prune`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(args || {}),
        });
        if (!res.ok) throw new Error(`Session prune failed: ${await res.text()}`);
        return await res.json();
      }

      // ── Actions ─────────────────────────────────────────────────────────
      case 'cassi_think_now': {
        const res = await fetchWithTimeout(`${CASSICORE_URL}/intelligence/thinker/think`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            sessionId: args?.sessionId,
            prompt: args?.prompt,
          }),
        });
        if (!res.ok) throw new Error(`Think trigger failed: ${await res.text()}`);
        return await res.json();
      }

      case 'cassi_strategy_update': {
        const action = args?.action || 'get';
        if (action === 'get') {
          const res = await fetchWithTimeout(`${CASSICORE_URL}/intelligence/thinker/strategy`);
          if (!res.ok) throw new Error(`Strategy get failed: ${await res.text()}`);
          return await res.json();
        } else if (action === 'set') {
          const res = await fetchWithTimeout(`${CASSICORE_URL}/intelligence/thinker/strategy`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(args.strategy || {}),
          });
          if (!res.ok) throw new Error(`Strategy set failed: ${await res.text()}`);
          return await res.json();
        } else if (action === 'reset') {
          const res = await fetchWithTimeout(`${CASSICORE_URL}/intelligence/thinker/strategy`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reset: true }),
          });
          if (!res.ok) throw new Error(`Strategy reset failed: ${await res.text()}`);
          return await res.json();
        }
        throw new Error(`Unknown strategy action: ${action}`);
      }

      case 'cassi_anomaly_ack': {
        const aid = encodeURIComponent(args.anomalyId);
        const res = await fetchWithTimeout(`${CASSICORE_URL}/intelligence/subconscious/anomalies/${aid}/acknowledge`, {
          method: 'POST',
        });
        if (!res.ok) throw new Error(`Anomaly acknowledge failed: ${await res.text()}`);
        return await res.json();
      }

      // ── Teams (multiplexed) ─────────────────────────────────────────────
      case 'cassi_team': {
        return await executeTeamAction(args);
      }

      default:
        throw new Error(`Unknown extended tool: ${toolName}`);
    }
  } catch (error: any) {
    log('error', 'Extended tool execution failed', { tool: toolName, error: error.message });
    throw error;
  }
}

/**
 * Handle multiplexed team operations via the "action" parameter
 */
async function executeTeamAction(args: any): Promise<any> {
  const action = args?.action;
  if (!action) throw new Error('Team tool requires an "action" parameter');

  switch (action) {
    case 'start': {
      const res = await fetchWithTimeout(`${CASSICORE_URL}/teams`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          goal: args.goal,
          name: args.name,
          budget: args.budget,
          roles: args.roles,
        }),
      });
      if (!res.ok) throw new Error(`Team start failed: ${await res.text()}`);
      return await res.json();
    }

    case 'status': {
      const qs = args.teamId ? `?teamId=${encodeURIComponent(args.teamId)}` : '';
      const res = await fetchWithTimeout(`${CASSICORE_URL}/teams/status${qs}`);
      if (!res.ok) throw new Error(`Team status failed: ${await res.text()}`);
      return await res.json();
    }

    case 'tree': {
      if (!args.teamId) throw new Error('Team "tree" action requires teamId');
      const res = await fetchWithTimeout(`${CASSICORE_URL}/teams/tree?teamId=${encodeURIComponent(args.teamId)}`);
      if (!res.ok) throw new Error(`Team tree failed: ${await res.text()}`);
      return await res.json();
    }

    case 'list': {
      const res = await fetchWithTimeout(`${CASSICORE_URL}/teams`);
      if (!res.ok) throw new Error(`Team list failed: ${await res.text()}`);
      return await res.json();
    }

    case 'pause':
    case 'resume':
    case 'cancel': {
      if (!args.teamId) throw new Error(`Team "${action}" action requires teamId`);
      const res = await fetchWithTimeout(`${CASSICORE_URL}/teams/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ teamId: args.teamId }),
      });
      if (!res.ok) throw new Error(`Team ${action} failed: ${await res.text()}`);
      return await res.json();
    }

    case 'checkpoints': {
      const params = new URLSearchParams();
      if (args.teamId) params.set('teamId', args.teamId);
      const qs = params.toString();
      const res = await fetchWithTimeout(`${CASSICORE_URL}/teams/checkpoints${qs ? '?' + qs : ''}`);
      if (!res.ok) throw new Error(`Team checkpoints failed: ${await res.text()}`);
      return await res.json();
    }

    case 'approve':
    case 'reject': {
      if (!args.checkpointId) throw new Error(`Team "${action}" action requires checkpointId`);
      const res = await fetchWithTimeout(`${CASSICORE_URL}/teams/checkpoints/${encodeURIComponent(args.checkpointId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision: action,
          feedback: args.feedback,
        }),
      });
      if (!res.ok) throw new Error(`Team ${action} failed: ${await res.text()}`);
      return await res.json();
    }

    case 'steer': {
      if (!args.teamId) throw new Error('Team "steer" action requires teamId');
      const res = await fetchWithTimeout(`${CASSICORE_URL}/teams/steer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          teamId: args.teamId,
          instructions: args.feedback,
        }),
      });
      if (!res.ok) throw new Error(`Team steer failed: ${await res.text()}`);
      return await res.json();
    }

    default:
      throw new Error(`Unknown team action: "${action}". Valid: start, status, tree, list, pause, resume, cancel, checkpoints, approve, reject, steer`);
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Intelligence Tool Execution & Markdown Formatters
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Helper to fetch JSON from an admin API endpoint.
 * Uses timeout to prevent indefinite hangs and validates Content-Type.
 */
async function fetchIntelligence(path: string, params?: Record<string, string>): Promise<any> {
  const url = new URL(path, CASSICORE_URL);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) url.searchParams.set(k, v);
    }
  }
  const response = await fetchWithTimeout(url.toString());
  if (!response.ok) {
    const text = await response.text().catch(() => '(unreadable body)');
    throw new Error(`Admin API error (${response.status}): ${text}`);
  }
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('json')) {
    const text = await response.text().catch(() => '');
    throw new Error(`Expected JSON from ${path}, got ${contentType}: ${text.slice(0, 200)}`);
  }
  return response.json();
}

/**
 * Resolve the most recent active session ID
 */
async function resolveSessionId(sessionId?: string): Promise<string | undefined> {
  if (sessionId) return sessionId;
  try {
    const data = await fetchIntelligence('/sessions');
    const sessions = data?.sessions;
    if (Array.isArray(sessions) && sessions.length > 0) {
      const sorted = sessions.sort((a: any, b: any) => (b.lastActiveAt || 0) - (a.lastActiveAt || 0));
      return sorted[0]?.id;
    }
  } catch {
    // Sessions endpoint may not be available
  }
  return undefined;
}

/**
 * Format cassi_activity output
 */
async function formatActivity(args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const data = await fetchIntelligence('/intelligence/activity');

  if (mode === 'brief') {
    const lines: string[] = ['## CassiCore Activity Brief\n'];
    
    const moduleCount = data.modules?.length || 0;
    lines.push(`**${moduleCount} modules active**`);

    // Thinker
    if (data.thinker?.stats) {
      const ts = data.thinker.stats;
      lines.push(`**Thinker**: ${ts.totalInsights || 0} insights generated, ${ts.turnsProcessed || 0} turns processed`);
    }

    // Dialectic
    if (data.dialectic) {
      const d = data.dialectic;
      lines.push(`**Dialectic**: ${d.totalTurns || 0} turns analyzed, ${d.signalsInjected || 0} signals injected (avg confidence: ${(d.avgConfidence || 0).toFixed(2)})`);
    }

    // Archive
    if (data.archive) {
      lines.push(`**Archive**: ${data.archive.totalEntries || 0} entries (${Object.keys(data.archive.byType || {}).length} types)`);
    }

    // Memory
    if (data.memory) {
      const totalMem = Object.values(data.memory).reduce((sum: number, v: any) => sum + (typeof v === 'number' ? v : 0), 0);
      lines.push(`**Memory**: ${totalMem} items stored`);
    }

    // Reflect
    if (data.reflect?.unresolvedPatterns?.length) {
      lines.push(`**Reflect**: ${data.reflect.unresolvedPatterns.length} unresolved patterns`);
    }

    // Optimizer
    const healthKeys = Object.keys(data.optimizer?.sessionHealth || {});
    if (healthKeys.length > 0) {
      lines.push(`**Optimizer**: tracking ${healthKeys.length} session(s)`);
    }

    // Consciousness / Subconscious
    const subconData = await fetchIntelligence('/intelligence/subconscious/stats').catch(() => null);
    const subconSnap = await fetchIntelligence('/intelligence/subconscious/debug').catch(() => null);
    if (subconData?.stats || subconSnap?.snapshot) {
      const stats = subconData?.stats ?? {};
      const snap = subconSnap?.snapshot ?? {};
      const health = snap.systemHealth ?? 'unknown';
      const badge = ({ healthy: '●', degraded: '◐', critical: '○' } as Record<string, string>)[health] ?? '?';
      const rate = typeof stats?.eventRate === 'number' ? ` | ${stats.eventRate.toFixed(1)} events/min` : '';
      const activeAnoms = stats?.activeAnomalies ?? 0;
      const anomNote = activeAnoms > 0 ? ` | **${activeAnoms} anomaly(ies)**` : '';
      const drones = snap?.activeDrones ?? 0;
      const teams = snap?.activeTeams ?? 0;
      const workNote = (drones > 0 || teams > 0) ? ` | ${drones} drones, ${teams} teams` : '';
      lines.push(`**Consciousness**: ${badge} ${health}${rate}${anomNote}${workNote}`);
    }

    // AI Scientist
    if (data.aiScientist?.recentStudies?.length) {
      lines.push(`**AI Scientist**: ${data.aiScientist.recentStudies.length} recent studies`);
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## CassiCore Activity Dashboard\n'];
  
  // Module table
  lines.push('### Modules\n');
  lines.push('| Module | Priority | Status |');
  lines.push('|--------|----------|--------|');
  for (const m of (data.modules || [])) {
    lines.push(`| ${m.name} | ${m.priority} | ${m.status} |`);
  }

  // Thinker section
  if (data.thinker?.stats) {
    lines.push('\n### Thinker\n');
    const ts = data.thinker.stats;
    for (const [k, v] of Object.entries(ts)) {
      lines.push(`- **${k}**: ${v}`);
    }
    if (data.thinker.strategy) {
      lines.push('\n**Current Strategy**:');
      lines.push('```json');
      lines.push(JSON.stringify(data.thinker.strategy, null, 2));
      lines.push('```');
    }
  }

  // Dialectic section
  if (data.dialectic) {
    lines.push('\n### Dialectic (Most Recent Session)\n');
    for (const [k, v] of Object.entries(data.dialectic)) {
      lines.push(`- **${k}**: ${typeof v === 'number' ? (Number.isInteger(v) ? v : (v as number).toFixed(3)) : v}`);
    }
  }

  // Archive section
  if (data.archive) {
    lines.push('\n### Archive\n');
    lines.push(`- **Total entries**: ${data.archive.totalEntries || 0}`);
    lines.push(`- **Avg importance**: ${(data.archive.avgImportance || 0).toFixed(3)}`);
    lines.push(`- **Thinking blocks**: ${data.archive.thinkingBlocksCount || 0}`);
    lines.push(`- **Linked entries**: ${data.archive.linkedEntriesCount || 0}`);
    if (data.archive.byType) {
      lines.push('\n**By Type**:');
      for (const [type, count] of Object.entries(data.archive.byType)) {
        lines.push(`  - ${type}: ${count}`);
      }
    }
  }

  // Reflect section
  if (data.reflect?.unresolvedPatterns?.length) {
    lines.push('\n### Reflect — Unresolved Patterns\n');
    for (const p of data.reflect.unresolvedPatterns) {
      lines.push(`- **${p.pattern || p.category || 'unknown'}**: ${p.occurrences || 1} occurrences`);
    }
  }

  // Optimizer section
  if (Object.keys(data.optimizer?.sessionHealth || {}).length > 0) {
    lines.push('\n### Optimizer — Session Health\n');
    lines.push('| Session | Health Score | Status |');
    lines.push('|---------|-------------|--------|');
    for (const [sid, health] of Object.entries(data.optimizer.sessionHealth)) {
      const h = health as any;
      lines.push(`| ${sid.slice(0, 12)}... | ${h.score?.toFixed(2) ?? 'N/A'} | ${h.status ?? 'unknown'} |`);
    }
  }

  // AI Scientist section
  if (data.aiScientist?.recentStudies?.length) {
    lines.push('\n### AI Scientist — Recent Studies\n');
    for (const study of data.aiScientist.recentStudies) {
      lines.push(`- **${study.title || 'Untitled'}** (confidence: ${(study.confidence || 0).toFixed(2)})`);
      if (study.conclusions) lines.push(`  ${study.conclusions.slice(0, 150)}${study.conclusions.length > 150 ? '...' : ''}`);
    }
  }

  // Memory section
  if (data.memory) {
    lines.push('\n### Memory\n');
    for (const [k, v] of Object.entries(data.memory)) {
      lines.push(`- **${k}**: ${v}`);
    }
  }

  // Consciousness section (full mode)
  const subconStats = await fetchIntelligence('/intelligence/subconscious/stats').catch(() => null);
  const subconDebug = await fetchIntelligence('/intelligence/subconscious/debug').catch(() => null);
  if (subconStats?.stats || subconDebug?.snapshot) {
    const stats = subconStats?.stats ?? {};
    const snap = subconDebug?.snapshot ?? {};
    lines.push('\n### Consciousness Observer\n');
    const health = snap.systemHealth ?? 'unknown';
    const badge = { healthy: '●', degraded: '◐', critical: '○' }[health] ?? '?';
    lines.push(`**System Health**: ${badge} ${health}`);
    if (stats.totalEvents != null) lines.push(`- **Total events seen**: ${stats.totalEvents}`);
    if (stats.eventRate != null) lines.push(`- **Event rate**: ${typeof stats.eventRate === 'number' ? stats.eventRate.toFixed(1) : stats.eventRate}/min`);
    if (stats.totalObservations != null) lines.push(`- **Observations**: ${stats.totalObservations}`);
    if (stats.activeAnomalies != null) lines.push(`- **Active anomalies**: ${stats.activeAnomalies}`);
    if (snap.activeDrones != null) lines.push(`- **Active drones**: ${snap.activeDrones}`);
    if (snap.activeTeams != null) lines.push(`- **Active teams**: ${snap.activeTeams}`);
    // Provider health
    const providerHealth: Record<string, string> = snap.providerHealth ?? {};
    const badProviders = Object.entries(providerHealth).filter(([, s]) => s !== 'healthy');
    if (badProviders.length > 0) {
      lines.push(`- **Provider issues**: ${badProviders.map(([id, s]) => `${id}:${s}`).join(', ')}`);
    }
    // Anomalies
    const anomData = await fetchIntelligence('/intelligence/subconscious/anomalies').catch(() => null);
    const anomalies: any[] = anomData?.anomalies ?? [];
    const unacked = anomalies.filter((a: any) => !a.acknowledged);
    if (unacked.length > 0) {
      lines.push(`\n**Unacknowledged anomalies** (${unacked.length}):`);
      for (const a of unacked.slice(0, 5)) {
        lines.push(`  - [${a.severity}] ${(a.description ?? '').slice(0, 80)}`);
      }
    }
  }

  return lines.join('\n');
}

/**
 * Format cassi_dialectic output
 */
async function formatDialectic(args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const limit = args?.limit || 5;
  const sessionId = await resolveSessionId(args?.sessionId);

  if (!sessionId) {
    return '## Dialectic\n\nNo active session found. Provide a `sessionId` parameter or start a conversation first.';
  }

  const [historyData, statsData] = await Promise.all([
    fetchIntelligence(`/dialectic/${sessionId}/history`, { limit: String(limit) }),
    fetchIntelligence(`/dialectic/${sessionId}/stats`).catch(() => null),
  ]);

  const history = historyData?.history || historyData?.turns || historyData || [];
  const stats = statsData?.stats || statsData;

  if (mode === 'brief') {
    const lines: string[] = [`## Dialectic Brief (session: ${sessionId.slice(0, 12)}...)\n`];

    if (stats) {
      lines.push(`**${stats.totalTurns || 0}** turns analyzed | **${stats.signalsInjected || 0}** signals injected | avg confidence: **${(stats.avgConfidence || 0).toFixed(2)}**`);
    }

    const recent = Array.isArray(history) ? history.slice(0, 3) : [];
    if (recent.length > 0) {
      lines.push('\n**Recent Analysis**:');
      for (const turn of recent) {
        const yang = turn.yang || turn.yang_output || turn.yangOutput;
        const synth = turn.serenity || turn.synthesizer_output || turn.synthesizerOutput;
        const injected = turn.signal_injected ?? turn.signalInjected;
        const yangSummary = typeof yang === 'string' ? yang.slice(0, 80) : (yang?.observation || yang?.summary || JSON.stringify(yang)).slice(0, 80);
        lines.push(`- ${injected ? '[INJECTED]' : '[observed]'} ${yangSummary}${yangSummary.length >= 80 ? '...' : ''}`);
      }
    } else {
      lines.push('\nNo dialectic turns recorded for this session yet.');
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = [`## Dialectic Dashboard (session: ${sessionId.slice(0, 12)}...)\n`];

  // Stats table
  if (stats) {
    lines.push('### Statistics\n');
    for (const [k, v] of Object.entries(stats)) {
      lines.push(`- **${k}**: ${typeof v === 'number' ? (Number.isInteger(v) ? v : (v as number).toFixed(3)) : v}`);
    }
  }

  // Turn history
  const turns = Array.isArray(history) ? history : [];
  if (turns.length > 0) {
    lines.push(`\n### Recent Turns (${turns.length})\n`);
    for (let i = 0; i < turns.length; i++) {
      const turn = turns[i];
      const yang = turn.yang || turn.yang_output || turn.yangOutput;
      const yin = turn.yin || turn.yin_output || turn.yinOutput;
      const synth = turn.serenity || turn.synthesizer_output || turn.synthesizerOutput;
      const injected = turn.signal_injected ?? turn.signalInjected;
      const latency = turn.total_latency_ms ?? turn.totalLatencyMs;

      lines.push(`#### Turn ${i + 1} ${injected ? '(SIGNAL INJECTED)' : ''}`);
      if (latency) lines.push(`*Latency: ${latency}ms*\n`);

      // Yang
      lines.push('**Yang (Creative Observer)**:');
      if (typeof yang === 'object' && yang !== null) {
        lines.push('```json');
        lines.push(JSON.stringify(yang, null, 2));
        lines.push('```');
      } else {
        lines.push(`> ${yang || 'N/A'}`);
      }

      // Yin
      lines.push('\n**Yin (Critical Analyst)**:');
      if (typeof yin === 'object' && yin !== null) {
        lines.push('```json');
        lines.push(JSON.stringify(yin, null, 2));
        lines.push('```');
      } else {
        lines.push(`> ${yin || 'N/A'}`);
      }

      // Synthesizer
      lines.push('\n**Synthesizer (Serenity)**:');
      if (typeof synth === 'object' && synth !== null) {
        lines.push('```json');
        lines.push(JSON.stringify(synth, null, 2));
        lines.push('```');
      } else {
        lines.push(`> ${synth || 'N/A'}`);
      }
      lines.push('');
    }
  } else {
    lines.push('\nNo dialectic turns recorded for this session.');
  }

  return lines.join('\n');
}

/**
 * Format cassi_thinker output
 */
async function formatThinker(args: any): Promise<string> {
  const mode = args?.mode || 'brief';

  const [statsData, strategyData, insightData] = await Promise.all([
    fetchIntelligence('/intelligence/thinker/stats').catch(() => null),
    fetchIntelligence('/intelligence/thinker/strategy').catch(() => null),
    fetchIntelligence('/intelligence/thinker/insight-history').catch(() => null),
  ]);

  const stats = statsData?.stats || statsData;
  const strategy = strategyData?.strategy || strategyData;
  const insights = insightData?.history || insightData?.insights || insightData;

  if (mode === 'brief') {
    const lines: string[] = ['## Thinker Brief\n'];

    if (stats) {
      lines.push(`**${stats.totalInsights || stats.insightCount || 0}** insights | **${stats.turnsProcessed || stats.turnCount || 0}** turns processed | enabled: **${stats.enabled ?? 'unknown'}**`);
    } else {
      lines.push('*Thinker stats not available*');
    }

    if (strategy) {
      const s = typeof strategy === 'string' ? JSON.parse(strategy) : strategy;
      lines.push(`\n**Strategy**: ponder interval ${s.ponderIntervalMs || s.ponderInterval || 'default'}ms, trigger sensitivity ${(s.triggerSensitivity || 0).toFixed(2)}`);
    }

    if (Array.isArray(insights) && insights.length > 0) {
      lines.push(`\n**Latest Insight** (${new Date(insights[0].timestamp || insights[0].createdAt || Date.now()).toLocaleString()}):`);
      const content = insights[0].content || insights[0].insight || JSON.stringify(insights[0]);
      lines.push(`> ${content.slice(0, 200)}${content.length > 200 ? '...' : ''}`);
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## Thinker Dashboard\n'];

  // Stats
  if (stats) {
    lines.push('### Runtime Stats\n');
    for (const [k, v] of Object.entries(stats)) {
      lines.push(`- **${k}**: ${v}`);
    }
  }

  // Strategy
  if (strategy) {
    lines.push('\n### Adaptive Strategy\n');
    const s = typeof strategy === 'string' ? JSON.parse(strategy) : strategy;
    lines.push('```json');
    lines.push(JSON.stringify(s, null, 2));
    lines.push('```');
  }

  // Insight History
  if (Array.isArray(insights) && insights.length > 0) {
    lines.push(`\n### Insight History (${insights.length} entries)\n`);
    for (const insight of insights.slice(0, 10)) {
      const content = insight.content || insight.insight || JSON.stringify(insight);
      const ts = insight.timestamp || insight.createdAt;
      const feedback = insight.feedbackScore ?? insight.feedback;
      lines.push(`#### ${ts ? new Date(ts).toLocaleString() : 'Unknown time'} ${feedback !== undefined ? `(feedback: ${feedback})` : ''}`);
      lines.push(`${content}\n`);
    }
  } else {
    lines.push('\n*No insight history available.*');
  }

  return lines.join('\n');
}

/**
 * Format cassi_subconscious output
 */
async function formatSubconscious(args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const sessionId = await resolveSessionId(args?.sessionId);

  const params: Record<string, string> = {};
  if (sessionId) params.sessionId = sessionId;

  const [debugData, statsData, anomaliesData] = await Promise.all([
    fetchIntelligence('/intelligence/subconscious/debug', params).catch(() => null),
    fetchIntelligence('/intelligence/subconscious/stats').catch(() => null),
    fetchIntelligence('/intelligence/subconscious/anomalies').catch(() => null),
  ]);

  const snap: Record<string, any> = debugData?.snapshot ?? {};
  const stats = statsData?.stats ?? statsData ?? {};
  const anomalies: any[] = anomaliesData?.anomalies ?? anomaliesData ?? [];
  const observations: any[] = debugData?.recentObservations ?? [];

  // ─── Helper: health badge ───────────────────────────────────────────────────
  const healthBadge = (h: string) => ({
    healthy: '● healthy',
    degraded: '◐ degraded',
    critical: '○ critical',
  }[h] ?? `? ${h}`);

  const providerBadge = (s: string) => ({
    healthy: '✓', degraded: '~', error: '✗', rate_limited: '⏸',
  }[s] ?? s);

  if (mode === 'brief') {
    const lines: string[] = ['## Conscious Observer Brief\n'];

    // System health + counts
    const health = snap.systemHealth ?? 'unknown';
    const sessionCount = snap.sessionCount ?? 0;
    const drones = snap.activeDrones ?? 0;
    const teams = snap.activeTeams ?? 0;
    const totalObs = stats.totalObservations ?? 0;
    const totalAnoms = stats.totalAnomalies ?? 0;
    const eventRate = typeof stats.eventRate === 'number' ? stats.eventRate.toFixed(1) : (stats.eventRate ?? '?');
    lines.push(`**System**: ${healthBadge(health)} | sessions: ${sessionCount} | events/min: ${eventRate}`);
    if (drones > 0 || teams > 0) {
      lines.push(`**Active**: ${drones} drone(s), ${teams} team(s)`);
    }
    lines.push(`**Observations**: ${totalObs} total | **Anomalies**: ${totalAnoms} total`);

    // Provider health issues
    const providerHealth: Record<string, string> = snap.providerHealth ?? {};
    const badProviders = Object.entries(providerHealth).filter(([, s]) => s !== 'healthy');
    if (badProviders.length > 0) {
      lines.push(`\n**Provider Issues**: ${badProviders.map(([id, s]) => `${id}: ${s}`).join(', ')}`);
    }

    // Plugin crashes
    const pluginStatus: Record<string, string> = snap.pluginStatus ?? {};
    const crashedPlugins = Object.entries(pluginStatus).filter(([, s]) => s === 'crashed');
    if (crashedPlugins.length > 0) {
      lines.push(`**Plugin Crashes**: ${crashedPlugins.map(([id]) => id).join(', ')}`);
    }

    // Budget warnings
    const budgetTiers: Record<string, string> = snap.budgetTiers ?? {};
    const urgentBudget = Object.entries(budgetTiers).filter(([, t]) => t === 'critical' || t === 'frugal');
    if (urgentBudget.length > 0) {
      lines.push(`**Budget Warnings**: ${urgentBudget.map(([id, t]) => `${id}: ${t}`).join(', ')}`);
    }

    // Recent patterns
    const patterns: string[] = (snap.recentPatterns ?? []).slice(0, 3);
    if (patterns.length > 0) {
      lines.push(`\n**Recent Patterns**: ${patterns.join(' · ')}`);
    }

    // Recent observations
    if (observations.length > 0) {
      lines.push(`\n**Recent Observations** (${observations.length}):`);
      for (const obs of observations.slice(0, 3)) {
        const src = obs.type ?? obs.source ?? 'observation';
        const conf = obs.confidence != null ? ` (${Math.round(obs.confidence * 100)}%)` : '';
        lines.push(`- [${src}${conf}] ${(obs.summary ?? obs.description ?? '').slice(0, 100)}`);
      }
    }

    // Unacknowledged anomalies
    const unacked = anomalies.filter((a: any) => !a.acknowledged);
    if (unacked.length > 0) {
      lines.push(`\n**${unacked.length} unacknowledged anomaly(ies)**:`);
      for (const a of unacked.slice(0, 3)) {
        lines.push(`- [${a.severity ?? '?'}] ${(a.description ?? '').slice(0, 80)}`);
      }
    }

    return lines.join('\n');
  }

  // ─── Full mode ─────────────────────────────────────────────────────────────
  const lines: string[] = [`## Conscious Observer Dashboard${sessionId ? ` (session: ${sessionId.slice(0, 12)}...)` : ''}\n`];

  // System health overview
  const health = snap.systemHealth ?? 'unknown';
  lines.push(`**System Health**: ${healthBadge(health)}\n`);

  // Stats summary
  if (Object.keys(stats).length > 0) {
    lines.push('### Statistics\n');
    const totalEvents = stats.totalEvents ?? '?';
    const activeSessions = stats.activeSessions ?? snap.sessionCount ?? '?';
    const eventRate = typeof stats.eventRate === 'number' ? stats.eventRate.toFixed(1) : (stats.eventRate ?? '?');
    const totalObs = stats.totalObservations ?? 0;
    const activeAnoms = stats.activeAnomalies ?? anomalies.filter((a: any) => !a.acknowledged).length;
    const avgConf = typeof stats.averageConfidence === 'number' ? stats.averageConfidence.toFixed(3) : '?';
    lines.push(`| Metric | Value |`);
    lines.push(`|--------|-------|`);
    lines.push(`| Total events seen | ${totalEvents} |`);
    lines.push(`| Active sessions | ${activeSessions} |`);
    lines.push(`| Events/min | ${eventRate} |`);
    lines.push(`| Total observations | ${totalObs} |`);
    lines.push(`| Active anomalies | ${activeAnoms} |`);
    lines.push(`| Avg observation confidence | ${avgConf} |`);
    if (snap.activeDrones != null || snap.activeTeams != null) {
      lines.push(`| Active drones | ${snap.activeDrones ?? 0} |`);
      lines.push(`| Active teams | ${snap.activeTeams ?? 0} |`);
    }
  }

  // Provider health table
  const providerHealth: Record<string, string> = snap.providerHealth ?? {};
  if (Object.keys(providerHealth).length > 0) {
    lines.push('\n### Provider Health\n');
    lines.push('| Provider | Status |');
    lines.push('|----------|--------|');
    for (const [id, status] of Object.entries(providerHealth)) {
      lines.push(`| ${id} | ${providerBadge(status)} ${status} |`);
    }
  }

  // Plugin status table
  const pluginStatus: Record<string, string> = snap.pluginStatus ?? {};
  if (Object.keys(pluginStatus).length > 0) {
    lines.push('\n### Plugin Status\n');
    lines.push('| Plugin | Status |');
    lines.push('|--------|--------|');
    for (const [id, status] of Object.entries(pluginStatus)) {
      lines.push(`| ${id} | ${status} |`);
    }
  }

  // Budget tiers table
  const budgetTiers: Record<string, string> = snap.budgetTiers ?? {};
  if (Object.keys(budgetTiers).length > 0) {
    lines.push('\n### Budget Tiers\n');
    lines.push('| Provider | Tier |');
    lines.push('|----------|------|');
    for (const [id, tier] of Object.entries(budgetTiers)) {
      lines.push(`| ${id} | ${tier} |`);
    }
  }

  // Top event types from stats
  if (Array.isArray(stats.topEventTypes) && stats.topEventTypes.length > 0) {
    lines.push('\n### Top Event Types\n');
    lines.push('| Type | Count |');
    lines.push('|------|-------|');
    for (const { type, count } of stats.topEventTypes) {
      lines.push(`| ${type} | ${count} |`);
    }
  }

  // Recent observations
  if (observations.length > 0) {
    lines.push(`\n### Recent Observations (${observations.length})\n`);
    for (const obs of observations) {
      const src = obs.type ?? obs.source ?? 'observation';
      const conf = obs.confidence != null ? ` (${Math.round(obs.confidence * 100)}%)` : '';
      const patterns = Array.isArray(obs.patterns) && obs.patterns.length > 0
        ? `\n  Patterns: ${obs.patterns.slice(0, 3).join(', ')}`
        : '';
      lines.push(`- **[${src}${conf}]** ${obs.summary ?? obs.description ?? ''}${patterns}`);
    }
  }

  // Anomalies table
  if (anomalies.length > 0) {
    lines.push(`\n### Anomalies (${anomalies.length})\n`);
    lines.push('| ID | Severity | Description | Acked |');
    lines.push('|----|----------|-------------|-------|');
    for (const a of anomalies) {
      const desc = (a.description ?? a.summary ?? '').slice(0, 60);
      lines.push(`| ${(a.id ?? '?').slice(0, 8)} | ${a.severity ?? '?'} | ${desc} | ${a.acknowledged ? 'Yes' : 'No'} |`);
    }
  }

  // Context injection preview
  if (debugData?.context) {
    lines.push('\n### Context Manager (preview)\n');
    lines.push('```json');
    lines.push(JSON.stringify(debugData.context, null, 2).slice(0, 2000));
    lines.push('```');
  }

  return lines.join('\n');
}


/**
 * Format cassi_consciousness output — live event stream + observer pipeline
 */
async function formatConsciousness(args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const windowSecs = args?.windowSecs ?? 60;

  const data = await fetchIntelligence('/intelligence/subconscious/stream', {
    windowSecs: String(windowSecs),
  }).catch(() => null);

  if (!data?.stream) {
    return '## Consciousness Stream\n\nUnable to reach daemon or subconscious not initialised.';
  }

  const s = data.stream;
  const ratePerMin = typeof s.eventsPerSecond === 'number'
    ? (s.eventsPerSecond * 60).toFixed(1)
    : '?';
  const lastSweepAgo = s.lastLLMSweepAgo != null
    ? `${Math.round(s.lastLLMSweepAgo / 1000)}s ago`
    : s.lastLLMSweepAt > 0 ? 'known' : 'never';

  if (mode === 'brief') {
    const lines: string[] = ['## Consciousness Stream (brief)\n'];
    lines.push(`**Window**: last ${windowSecs}s | **Events**: ${s.totalEvents} | **Rate**: ${ratePerMin}/min`);
    lines.push(`**Active sessions**: ${s.activeSessions} | **Heuristic obs**: ${s.heuristicObservationCount} | **LLM obs**: ${s.llmObservationCount}`);
    lines.push(`**Last LLM sweep**: ${lastSweepAgo}`);

    if (Array.isArray(s.topEventTypes) && s.topEventTypes.length > 0) {
      const top5 = s.topEventTypes.slice(0, 5).map((t: any) => `${t.type}(${t.count})`).join(', ');
      lines.push(`\n**Top types**: ${top5}`);
    }

    if (Array.isArray(s.recentSequence) && s.recentSequence.length > 0) {
      lines.push(`\n**Recent sequence**: \`${s.recentSequence.slice(-8).join(' → ')}\``);
    }

    const recentLLM: any[] = s.recentLLMObservations ?? [];
    if (recentLLM.length > 0) {
      lines.push(`\n**Latest LLM sweep** (confidence: ${Math.round((recentLLM[0].confidence ?? 0) * 100)}%):`);
      lines.push(`> ${(recentLLM[0].summary ?? '').slice(0, 150)}`);
      if (recentLLM[0].concerns?.length > 0) {
        lines.push(`> Concerns: ${recentLLM[0].concerns.slice(0, 2).join('; ')}`);
      }
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = [`## Consciousness Stream (full) — last ${windowSecs}s\n`];
  lines.push(`| Metric | Value |`);
  lines.push(`|--------|-------|`);
  lines.push(`| Total events | ${s.totalEvents} |`);
  lines.push(`| Events/min | ${ratePerMin} |`);
  lines.push(`| Active sessions | ${s.activeSessions} |`);
  lines.push(`| Heuristic observations | ${s.heuristicObservationCount} |`);
  lines.push(`| LLM observations | ${s.llmObservationCount} |`);
  lines.push(`| Last LLM sweep | ${lastSweepAgo} |`);

  if (Array.isArray(s.topEventTypes) && s.topEventTypes.length > 0) {
    lines.push('\n### Event Type Distribution\n');
    lines.push('| Type | Count |');
    lines.push('|------|-------|');
    for (const { type, count } of s.topEventTypes) {
      lines.push(`| ${type} | ${count} |`);
    }
  }

  if (Array.isArray(s.recentSequence) && s.recentSequence.length > 0) {
    lines.push('\n### Recent Event Sequence\n');
    lines.push('```');
    lines.push(s.recentSequence.join(' → '));
    lines.push('```');
  }

  const recentLLM: any[] = s.recentLLMObservations ?? [];
  if (recentLLM.length > 0) {
    lines.push(`\n### LLM Sweep History (last ${recentLLM.length})\n`);
    for (const obs of recentLLM) {
      const ago = obs.timestamp ? `${Math.round((Date.now() - obs.timestamp) / 1000)}s ago` : '';
      lines.push(`#### Sweep ${ago} (${obs.eventCount} events, confidence: ${Math.round((obs.confidence ?? 0) * 100)}%)\n`);
      lines.push(`**Summary**: ${obs.summary ?? ''}`);
      if (obs.patterns?.length > 0) lines.push(`**Patterns**: ${obs.patterns.join(', ')}`);
      if (obs.concerns?.length > 0) lines.push(`**Concerns**: ${obs.concerns.join('; ')}`);
      if (obs.opportunities?.length > 0) lines.push(`**Opportunities**: ${obs.opportunities.join('; ')}`);
    }
  }

  return lines.join('\n');
}

/**
 * Format cassi_trace output — forensic turn reconstruction
 */
async function formatTrace(args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const sessionId = await resolveSessionId(args?.sessionId);
  if (!sessionId) {
    return '## Trace\n\nNo active session found. Provide a sessionId parameter.';
  }

  const params: Record<string, string> = { sessionId };
  if (args?.turnIndex !== undefined) params.turnIndex = String(args.turnIndex);
  if (args?.limit) params.limit = String(args.limit);

  const data = await fetchIntelligence('/intelligence/trace', params);

  if (mode === 'brief') {
    const lines: string[] = ['## Turn Trace (Brief)\n'];
    lines.push(`**Session**: \`${sessionId.slice(0, 12)}...\`\n`);

    // Continuity — recent turns
    const turns = data.continuity?.turns || [];
    if (turns.length > 0) {
      const latest = turns[turns.length - 1];
      lines.push(`**Latest turn**: ${latest.role} at ${new Date(latest.timestamp).toLocaleTimeString()} (${latest.content?.slice(0, 80)}...)`);
      lines.push(`**Turn context**: ${turns.length} turn(s) in window`);
    } else {
      lines.push('**No turn data** available for this session');
    }

    // Injections
    const injections = data.injections || [];
    if (injections.length > 0) {
      const sources = [...new Set(injections.map((i: any) => i.metadata?.source || i.category || 'unknown'))];
      lines.push(`**Injections**: ${injections.length} from ${sources.join(', ')}`);
    } else {
      lines.push('**Injections**: none recorded (ledger may not have been active)');
    }

    // Dialectic
    if (data.dialectic && data.dialectic.length > 0) {
      const latest = data.dialectic[data.dialectic.length - 1];
      lines.push(`**Dialectic**: last analysis at ${new Date(latest.timestamp || latest.created_at).toLocaleTimeString()} — ${latest.synthesis?.slice(0, 100) || 'no synthesis'}...`);
    }

    // Reflect patterns
    if (data.reflectPatterns?.length) {
      lines.push(`**Active patterns**: ${data.reflectPatterns.length} unresolved reflection pattern(s) may have influenced response`);
    }

    // Mental model
    if (data.mentalModel) {
      lines.push(`**Mental model**: active for this session`);
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## Turn Trace (Full Forensic)\n'];
  lines.push(`**Session**: \`${sessionId}\`  `);
  lines.push(`**Timestamp**: ${new Date(data.timestamp).toISOString()}\n`);

  // Continuity turns
  const turns = data.continuity?.turns || [];
  if (turns.length > 0) {
    lines.push('### Conversation Context\n');
    lines.push(`Total turns in window: ${data.continuity?.totalTurns || turns.length}\n`);
    lines.push('| # | Role | Time | Content (preview) |');
    lines.push('|---|------|------|--------------------|');
    turns.forEach((t: any, i: number) => {
      const time = new Date(t.timestamp).toLocaleTimeString();
      const preview = (t.content || '').replace(/\|/g, '\\|').slice(0, 60);
      lines.push(`| ${i} | ${t.role} | ${time} | ${preview}... |`);
    });
  }

  // Injection ledger
  const injections = data.injections || [];
  if (injections.length > 0) {
    lines.push('\n### Injection Ledger\n');
    lines.push('| Source | Time | Content (preview) |');
    lines.push('|--------|------|--------------------|');
    for (const inj of injections) {
      const source = inj.metadata?.source || inj.category || 'unknown';
      const time = inj.metadata?.turnTimestamp ? new Date(inj.metadata.turnTimestamp).toLocaleTimeString() : 'N/A';
      const preview = (inj.content || '').replace(/\|/g, '\\|').slice(0, 80);
      lines.push(`| ${source} | ${time} | ${preview}... |`);
    }
  } else {
    lines.push('\n### Injection Ledger\n');
    lines.push('No injection records found. The injection ledger persists entries from optimizer, thinker, dialectic, subconscious, and session digest modules.');
  }

  // Dialectic analysis
  if (data.dialectic && data.dialectic.length > 0) {
    lines.push('\n### Dialectic Analysis\n');
    for (const d of data.dialectic) {
      lines.push(`**Turn** at ${new Date(d.timestamp || d.created_at).toLocaleTimeString()}:`);
      if (d.yang) lines.push(`- **Yang**: ${d.yang.slice(0, 150)}...`);
      if (d.yin) lines.push(`- **Yin**: ${d.yin.slice(0, 150)}...`);
      if (d.synthesis) lines.push(`- **Synthesis**: ${d.synthesis.slice(0, 150)}...`);
      if (d.confidence !== undefined) lines.push(`- **Confidence**: ${(d.confidence * 100).toFixed(0)}%`);
      lines.push('');
    }
  }

  // Reflect patterns
  if (data.reflectPatterns?.length) {
    lines.push('\n### Active Reflection Patterns\n');
    for (const p of data.reflectPatterns) {
      lines.push(`- **${p.pattern || p.category || 'unknown'}** (${p.occurrences || 1}x): ${p.description || p.evidence || 'no description'}`);
    }
  }

  // Archive context
  if (data.archiveContext?.length) {
    lines.push('\n### Archive Context\n');
    for (const a of data.archiveContext) {
      lines.push(`- [${a.type}] ${(a.content || '').slice(0, 120)}...`);
    }
  }

  // Mental model
  if (data.mentalModel) {
    lines.push('\n### Mental Model State\n');
    lines.push('```json');
    lines.push(JSON.stringify(data.mentalModel, null, 2).slice(0, 500));
    lines.push('```');
  }

  return lines.join('\n');
}

/**
 * Format cassi_effectiveness output — outcome tracking metrics
 */
async function formatEffectiveness(args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const sessionId = await resolveSessionId(args?.sessionId);
  const windowMs = ((args?.windowHours || 24) * 60 * 60_000).toString();

  const [statsData, feedbackData] = await Promise.all([
    fetchIntelligence('/intelligence/outcomes/stats').catch(() => null),
    sessionId
      ? fetchIntelligence('/intelligence/outcomes/feedback', { sessionId, limit: '10' }).catch(() => null)
      : Promise.resolve(null),
  ]);

  const stats = statsData || {};
  const feedback = feedbackData?.feedback || [];

  if (mode === 'brief') {
    const lines: string[] = ['## Effectiveness Brief\n'];

    if (!statsData) {
      lines.push('OutcomeTracker not initialized or no data available.');
      return lines.join('\n');
    }

    lines.push(`**Total feedback detected**: ${stats.totalFeedbackDetected || 0}`);
    lines.push(`**Outcomes recorded**: ${stats.totalOutcomesRecorded || 0} insights, ${stats.totalToolOutcomesRecorded || 0} tools`);
    lines.push(`**Sessions tracked**: ${stats.trackedSessions || 0}`);
    lines.push(`**Pending**: ${stats.pendingFeedback || 0} feedback, ${stats.pendingToolOutcomes || 0} tool outcomes`);

    if (feedback.length > 0) {
      const positive = feedback.filter((f: any) => f.sentiment === 'positive' || f.score > 0).length;
      const negative = feedback.filter((f: any) => f.sentiment === 'negative' || f.score < 0).length;
      lines.push(`\n**Recent feedback** (${sessionId?.slice(0, 12)}...): ${positive} positive, ${negative} negative out of ${feedback.length}`);
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## Effectiveness Dashboard\n'];

  // Stats overview
  lines.push('### Aggregate Stats\n');
  lines.push('| Metric | Value |');
  lines.push('|--------|-------|');
  for (const [k, v] of Object.entries(stats)) {
    lines.push(`| ${k} | ${v} |`);
  }

  // Recent feedback
  if (feedback.length > 0) {
    lines.push(`\n### Recent Feedback (${sessionId?.slice(0, 12)}...)\n`);
    lines.push('| Sentiment | Score | Signal | Timestamp |');
    lines.push('|-----------|-------|--------|-----------|');
    for (const f of feedback) {
      const time = f.timestamp ? new Date(f.timestamp).toLocaleTimeString() : 'N/A';
      lines.push(`| ${f.sentiment || 'neutral'} | ${f.score ?? 'N/A'} | ${(f.signal || f.content || '').slice(0, 60)} | ${time} |`);
    }
  }

  // Source stats for common sources
  const sources = ['thinker', 'dialectic', 'subconscious', 'optimizer'];
  const sourceResults = await Promise.all(
    sources.map(s => fetchIntelligence(`/intelligence/outcomes/sources/${s}`, { windowMs }).catch(() => null))
  );
  const hasSourceData = sourceResults.some(r => r?.stats);
  if (hasSourceData) {
    lines.push('\n### Per-Source Quality\n');
    lines.push('| Source | Total | Avg Score | Positive Rate | Negative Rate |');
    lines.push('|--------|-------|-----------|---------------|---------------|');
    sources.forEach((s, i) => {
      const st = sourceResults[i]?.stats;
      if (st) {
        lines.push(`| ${s} | ${st.totalOutcomes} | ${st.avgScore?.toFixed(2) ?? 'N/A'} | ${(st.positiveRate * 100).toFixed(0)}% | ${(st.negativeRate * 100).toFixed(0)}% |`);
      }
    });
  }

  return lines.join('\n');
}

/**
 * Format cassi_budget output — provider usage metrics
 */
async function formatBudget(args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const opts: Record<string, string> = {};
  if (args?.providerId) opts.providerId = args.providerId;
  if (args?.model) opts.model = args.model;
  const hours = args?.hours || 24;

  const [statsData, aggregateData, hourlyData, budgetData] = await Promise.all([
    fetchIntelligence('/intelligence/profiler/stats').catch(() => null),
    fetchIntelligence('/intelligence/profiler/aggregate', opts).catch(() => null),
    fetchIntelligence('/intelligence/profiler/hourly', { ...opts, hours: String(hours) }).catch(() => null),
    fetchIntelligence('/intelligence/budget', opts).catch(() => null),
  ]);

  const stats = statsData || {};
  const aggregate = aggregateData?.aggregate || [];
  const hourly = hourlyData?.hourly || [];
  const budgetSnapshots = budgetData?.snapshots || [];
  const budgetTiers = budgetData?.tiers || {};

  if (mode === 'brief') {
    const lines: string[] = ['## Budget Brief\n'];

    // Budget tracker data (monthly limits, usage, tiers)
    if (budgetSnapshots.length > 0) {
      for (const snap of budgetSnapshots) {
        const tier = budgetTiers[snap.providerId] || 'unknown';
        const pct = ((snap.percentUsed || 0) * 100).toFixed(1);
        const exhaustion = snap.projectedExhaustionDay
          ? `projected exhaustion: day ${snap.projectedExhaustionDay}`
          : 'sustainable pace';
        lines.push(`**${snap.providerId}**: ${snap.used}/${snap.monthlyLimit} requests (${pct}%), tier: **${tier}**, ${exhaustion}`);
        lines.push(`  Burn rate: ~${snap.dailyBurnRate?.toFixed(1) || '?'} req/day, ${snap.remaining} remaining\n`);
      }
    }

    if (!statsData && budgetSnapshots.length === 0) {
      lines.push('No budget or profiler data available.');
      return lines.join('\n');
    }

    if (statsData) {
      lines.push(`**Total requests**: ${stats.totalRequestsRecorded || 0} (${stats.totalErrors || 0} errors)`);
      lines.push(`**Inflight**: ${stats.inflightRequests || 0} | **Pending records**: ${stats.pendingRecords || 0}`);

      if (aggregate.length > 0) {
        lines.push('\n**Provider breakdown**:');
        for (const a of aggregate.slice(0, 5)) {
          const errPct = a.totalRequests > 0 ? ((a.errorCount / a.totalRequests) * 100).toFixed(1) : '0';
          lines.push(`- **${a.providerId}/${a.model}**: ${a.totalRequests} req, ${a.totalTokens || 0} tokens, ${errPct}% errors, avg ${a.avgDurationMs?.toFixed(0) || '?'}ms`);
        }
      }
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## Budget Dashboard\n'];

  // Budget tracker section
  if (budgetSnapshots.length > 0) {
    lines.push('### Monthly Budget\n');
    lines.push('| Provider | Used | Limit | % Used | Tier | Burn Rate | Remaining | Exhaustion |');
    lines.push('|----------|------|-------|--------|------|-----------|-----------|------------|');
    for (const snap of budgetSnapshots) {
      const tier = budgetTiers[snap.providerId] || 'unknown';
      const pct = ((snap.percentUsed || 0) * 100).toFixed(1);
      const exhaustion = snap.projectedExhaustionDay ? `Day ${snap.projectedExhaustionDay}` : 'Sustainable';
      lines.push(`| ${snap.providerId} | ${snap.used} | ${snap.monthlyLimit} | ${pct}% | ${tier} | ${snap.dailyBurnRate?.toFixed(1) || '?'}/day | ${snap.remaining} | ${exhaustion} |`);
    }
  }

  // Aggregate stats
  lines.push('\n### Request Overview\n');
  lines.push('| Metric | Value |');
  lines.push('|--------|-------|');
  for (const [k, v] of Object.entries(stats)) {
    lines.push(`| ${k} | ${v} |`);
  }

  // Per-provider aggregate
  if (aggregate.length > 0) {
    lines.push('\n### Provider Aggregate\n');
    lines.push('| Provider | Model | Requests | Tokens | Errors | Avg Duration |');
    lines.push('|----------|-------|----------|--------|--------|-------------|');
    for (const a of aggregate) {
      lines.push(`| ${a.providerId} | ${a.model || 'all'} | ${a.totalRequests} | ${a.totalTokens || 0} | ${a.errorCount || 0} | ${a.avgDurationMs?.toFixed(0) || 'N/A'}ms |`);
    }
  }

  // Hourly trends
  if (hourly.length > 0) {
    lines.push(`\n### Hourly Trends (last ${hours}h)\n`);
    lines.push('| Hour | Requests | Tokens | Errors | Avg Duration |');
    lines.push('|------|----------|--------|--------|-------------|');
    for (const h of hourly.slice(-12)) {
      lines.push(`| ${h.hour || h.hourBucket} | ${h.requests || h.totalRequests} | ${h.tokens || h.totalTokens || 0} | ${h.errors || h.errorCount || 0} | ${h.avgDurationMs?.toFixed(0) || 'N/A'}ms |`);
    }
  }

  return lines.join('\n');
}

/**
 * Format cassi_evolution output — strategy self-modification timeline
 */
async function formatEvolution(args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const limit = args?.limit || 10;
  const module = args?.module;

  const [statsData, dialecticEffData] = await Promise.all([
    fetchIntelligence('/intelligence/strategy/stats').catch(() => null),
    fetchIntelligence('/intelligence/strategy/dialectic-effectiveness', { limit: String(limit) }).catch(() => null),
  ]);

  // Strategy history and best require a module name
  let historyData: any = null;
  let bestData: any = null;
  if (module) {
    [historyData, bestData] = await Promise.all([
      fetchIntelligence('/intelligence/strategy/history', { module, limit: String(limit) }).catch(() => null),
      fetchIntelligence('/intelligence/strategy/best', { module }).catch(() => null),
    ]);
  }

  const stats = statsData || {};
  const effectiveness = dialecticEffData?.effectiveness || [];

  if (mode === 'brief') {
    const lines: string[] = ['## Evolution Brief\n'];

    if (!statsData) {
      lines.push('StrategyTracker not initialized or no data available.');
      return lines.join('\n');
    }

    lines.push(`**Strategy snapshots**: ${stats.totalSnapshotsRecorded || 0}`);
    lines.push(`**Evaluations**: ${stats.totalEvaluations || 0}`);
    lines.push(`**Pending**: ${stats.pendingChanges || 0} changes, ${stats.pendingSignals || 0} signals`);

    if (bestData?.strategy) {
      const best = bestData.strategy;
      lines.push(`\n**Best strategy for \`${module}\`**: score ${best.score?.toFixed(3) ?? 'N/A'} (${new Date(best.timestamp || best.created_at).toLocaleDateString()})`);
    } else if (module) {
      lines.push(`\nNo best strategy found for \`${module}\`.`);
    } else {
      lines.push('\nProvide a `module` parameter (e.g., "thinker", "dialectic") to see strategy history.');
    }

    if (effectiveness.length > 0) {
      const avgEff = effectiveness.reduce((sum: number, e: any) => sum + (e.effectivenessScore || 0), 0) / effectiveness.length;
      lines.push(`**Dialectic effectiveness**: avg ${(avgEff * 100).toFixed(1)}% across ${effectiveness.length} sessions`);
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## Evolution Dashboard\n'];

  // Stats
  lines.push('### Overview\n');
  lines.push('| Metric | Value |');
  lines.push('|--------|-------|');
  for (const [k, v] of Object.entries(stats)) {
    lines.push(`| ${k} | ${v} |`);
  }

  // Strategy history for module
  const history = historyData?.history || [];
  if (history.length > 0) {
    lines.push(`\n### Strategy History: \`${module}\`\n`);
    lines.push('| Date | Score | Config (preview) |');
    lines.push('|------|-------|------------------|');
    for (const h of history) {
      const date = new Date(h.timestamp || h.created_at).toLocaleString();
      const config = (typeof h.configJson === 'string' ? h.configJson : JSON.stringify(h.configJson || {})).slice(0, 80);
      lines.push(`| ${date} | ${h.score?.toFixed(3) ?? 'N/A'} | ${config}... |`);
    }
  } else if (module) {
    lines.push(`\n### Strategy History: \`${module}\`\n`);
    lines.push('No history found for this module.');
  }

  // Best strategy
  if (bestData?.strategy) {
    lines.push(`\n### Best Strategy: \`${module}\`\n`);
    lines.push('```json');
    lines.push(JSON.stringify(bestData.strategy, null, 2));
    lines.push('```');
  }

  // Dialectic effectiveness
  if (effectiveness.length > 0) {
    lines.push('\n### Dialectic Session Effectiveness\n');
    lines.push('| Session | Effectiveness | Turns | Signals Injected |');
    lines.push('|---------|--------------|-------|-----------------|');
    for (const e of effectiveness) {
      lines.push(`| ${(e.sessionId || '').slice(0, 12)}... | ${((e.effectivenessScore || 0) * 100).toFixed(1)}% | ${e.totalTurns || 'N/A'} | ${e.signalsInjected || 'N/A'} |`);
    }
  }

  return lines.join('\n');
}

/**
 * Format cassi_blindspots output — cross-session pattern detection
 */
async function formatBlindspots(args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const opts: Record<string, string> = {};
  if (args?.category) opts.category = args.category;
  if (args?.minConfidence !== undefined) opts.minConfidence = String(args.minConfidence);
  opts.limit = String(args?.limit || 10);

  const [statsData, patternsData, reflectData] = await Promise.all([
    fetchIntelligence('/intelligence/correlator/stats').catch(() => null),
    fetchIntelligence('/intelligence/correlator/patterns', opts).catch(() => null),
    fetchIntelligence('/intelligence/activity').then(d => d?.reflect?.unresolvedPatterns).catch(() => null),
  ]);

  const stats = statsData || {};
  const patterns = patternsData?.patterns || [];
  const unresolvedPatterns = reflectData || [];

  if (mode === 'brief') {
    const lines: string[] = ['## Blindspots Brief\n'];

    if (!statsData) {
      lines.push('CrossSessionCorrelator not initialized or no data available.');
      return lines.join('\n');
    }

    lines.push(`**Patterns detected**: ${stats.totalPatternsDetected || 0} (${stats.storedPatterns || 0} stored)`);

    // Category breakdown
    if (stats.byCategory && Object.keys(stats.byCategory).length > 0) {
      const categories = Object.entries(stats.byCategory).sort((a: any, b: any) => b[1] - a[1]);
      lines.push(`**Categories**: ${categories.map(([k, v]) => `${k}(${v})`).join(', ')}`);
    }

    // Top patterns
    if (patterns.length > 0) {
      lines.push(`\n**Top ${Math.min(patterns.length, 3)} patterns**:`);
      for (const p of patterns.slice(0, 3)) {
        lines.push(`- [${p.category || 'uncategorized'}] ${(p.description || p.pattern || '').slice(0, 100)} (confidence: ${((p.confidence || 0) * 100).toFixed(0)}%)`);
      }
    }

    // Unresolved reflection patterns
    if (unresolvedPatterns.length > 0) {
      lines.push(`\n**Unresolved reflection patterns**: ${unresolvedPatterns.length}`);
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## Blindspots Dashboard\n'];

  // Stats
  lines.push('### Cross-Session Correlator Stats\n');
  lines.push('| Metric | Value |');
  lines.push('|--------|-------|');
  lines.push(`| Total patterns detected | ${stats.totalPatternsDetected || 0} |`);
  lines.push(`| Stored patterns | ${stats.storedPatterns || 0} |`);
  lines.push(`| Last run | ${stats.lastRunAt ? new Date(stats.lastRunAt).toLocaleString() : 'never'} |`);

  if (stats.byCategory && Object.keys(stats.byCategory).length > 0) {
    lines.push('\n**By Category**:');
    for (const [cat, count] of Object.entries(stats.byCategory)) {
      lines.push(`- ${cat}: ${count}`);
    }
  }

  // Cross-session patterns
  if (patterns.length > 0) {
    lines.push('\n### Detected Patterns\n');
    lines.push('| Category | Confidence | Description |');
    lines.push('|----------|------------|-------------|');
    for (const p of patterns) {
      lines.push(`| ${p.category || 'uncategorized'} | ${((p.confidence || 0) * 100).toFixed(0)}% | ${(p.description || p.pattern || '').slice(0, 100)} |`);
    }

    // Show full details for top patterns
    lines.push('\n### Pattern Details\n');
    for (const p of patterns.slice(0, 5)) {
      lines.push(`#### ${p.category || 'Pattern'} (${((p.confidence || 0) * 100).toFixed(0)}% confidence)\n`);
      lines.push(`- **Key**: ${p.correlationKey || 'N/A'}`);
      lines.push(`- **Description**: ${p.description || p.pattern || 'N/A'}`);
      if (p.evidence) lines.push(`- **Evidence**: ${typeof p.evidence === 'string' ? p.evidence.slice(0, 200) : JSON.stringify(p.evidence).slice(0, 200)}`);
      if (p.sessionIds) lines.push(`- **Sessions**: ${Array.isArray(p.sessionIds) ? p.sessionIds.length : 'N/A'}`);
      lines.push('');
    }
  }

  // Unresolved reflection patterns
  if (unresolvedPatterns.length > 0) {
    lines.push('\n### Unresolved Reflection Patterns\n');
    lines.push('These error/concern patterns from the Reflect module remain unresolved:\n');
    for (const p of unresolvedPatterns) {
      lines.push(`- **${p.pattern || p.category || 'unknown'}** (${p.occurrences || 1}x): ${p.description || p.evidence || 'no description'}`);
    }
  }

  return lines.join('\n');
}

/**
 * Format cassi_snapshot output — comprehensive team agent snapshot
 */
async function formatSnapshot(args: any): Promise<string> {
  const teamId = args?.teamId;
  const includeMessages = args?.includeMessages !== false;
  const messageLimit = args?.messageLimit || 5;

  const lines: string[] = ['# CassiCore Agent Snapshot\n'];
  lines.push(`*Generated: ${new Date().toISOString()}*\n`);

  try {
    // Get teams data
    const teamsData = await fetchIntelligence('/teams');
    let teams = teamsData?.teams || [];

    // Filter to specific team if requested
    if (teamId) {
      teams = teams.filter((t: any) => t.id === teamId);
      if (teams.length === 0) {
        return `# CassiCore Agent Snapshot\n\n**Error**: Team "${teamId}" not found.`;
      }
    }

    // Filter to running/paused teams only (show active work)
    const activeTeams = teams.filter((t: any) => t.status === 'running' || t.status === 'paused');
    const displayTeams = activeTeams.length > 0 ? activeTeams : teams;

    if (displayTeams.length === 0) {
      lines.push('## No Active Teams\n');
      lines.push('No teams are currently running. Use `cassi_team` with action "list" to see all teams.');
    } else {
      lines.push(`## Active Teams (${displayTeams.length})\n`);

      // Process each team
      for (const team of displayTeams) {
        const tid = team.id;
        
        // Get detailed team status
        const statusRes = await fetchWithTimeout(`${CASSICORE_URL}/teams/status?teamId=${encodeURIComponent(tid)}`);
        const statusData = statusRes.ok ? await statusRes.json() : null;
        
        // Get agents list
        const agentsRes = await fetchWithTimeout(`${CASSICORE_URL}/teams/agent/list?teamId=${encodeURIComponent(tid)}`);
        const agentsData = agentsRes.ok ? await agentsRes.json() : null;
        
        // Get checkpoints
        const checkpointsRes = await fetchWithTimeout(`${CASSICORE_URL}/teams/checkpoints?teamId=${encodeURIComponent(tid)}`);
        const checkpointsData = checkpointsRes.ok ? await checkpointsRes.json() : null;

        // Team header
        lines.push(`### Team: ${tid}`);
        lines.push(`**Goal:** ${team.goal || 'No goal set'}`);
        
        const progress = statusData?.progress;
        if (progress) {
          lines.push(`**Progress:** ${progress.completed || 0}/${progress.total || 0} goals (${progress.percentage || 0}%)`);
        }
        
        lines.push(`**Status:** ${team.status} | **Agents:** ${team.agentCount || 0} | **Started:** ${team.startedAt ? new Date(team.startedAt).toLocaleString() : 'N/A'}`);
        
        if (statusData?.team?.budget) {
          const b = statusData.team.budget;
          lines.push(`**Budget:** ${b.tokensUsed?.toLocaleString() || 0} tokens used${b.maxTokens ? ` / ${b.maxTokens.toLocaleString()} max` : ''}`);
        }
        lines.push('');

        // Agents section
        const agents = agentsData?.agents || [];
        if (agents.length > 0) {
          lines.push('#### Agents\n');
          
          for (const agent of agents) {
            const role = agent.isCoordinator ? 'coordinator' : (agent.roleHint || 'agent');
            const statusEmoji = agent.goalStatus === 'completed' ? '✓' : 
                               agent.goalStatus === 'in_progress' ? '▶' : 
                               agent.goalStatus === 'failed' ? '✗' : '○';
            
            lines.push(`- **${agent.agentId}** (${role}): ${agent.goalTitle || 'No goal'} ${statusEmoji}`);
            
            // Get recent messages if requested
            if (includeMessages) {
              try {
                const sessionRes = await fetchWithTimeout(`${CASSICORE_URL}/sessions?limit=50`);
                if (sessionRes.ok) {
                  const sessionsData = await sessionRes.json();
                  const agentSession = sessionsData?.sessions?.find((s: any) => 
                    s.id?.includes(agent.agentId) || s.agentId === agent.agentId
                  );
                  
                  if (agentSession?.id) {
                    const msgRes = await fetchWithTimeout(`${CASSICORE_URL}/sessions/${encodeURIComponent(agentSession.id)}/messages?limit=${messageLimit}`);
                    if (msgRes.ok) {
                      const msgData = await msgRes.json();
                      const recentMsgs = msgData?.messages?.slice(-messageLimit) || [];
                      
                      if (recentMsgs.length > 0) {
                        const lastMsg = recentMsgs[recentMsgs.length - 1];
                        const preview = (lastMsg.content || lastMsg.text || '').slice(0, 100);
                        if (preview) {
                          lines.push(`  > Last: "${preview}${preview.length >= 100 ? '...' : ''}"`);
                        }
                      }
                    }
                  }
                }
              } catch (msgErr) {
                // Silently skip message fetching errors
              }
            }
          }
          lines.push('');
        }

        // Checkpoints section
        const checkpoints = checkpointsData?.checkpoints || [];
        if (checkpoints.length > 0) {
          lines.push('#### Pending Checkpoints\n');
          for (const cp of checkpoints) {
            lines.push(`- **${cp.checkpointId}**: ${cp.description || 'No description'} (${cp.status})`);
          }
          lines.push('');
        }

        lines.push('---\n');
      }
    }

    // Git status section
    lines.push('## Git Status\n');
    try {
      const { execSync } = await import('child_process');
      const cwd = process.cwd();
      
      // Get short status
      const statusOutput = execSync('git status --short', { cwd, encoding: 'utf-8', timeout: 5000 });
      // Get diff stat
      const diffStatOutput = execSync('git diff --stat', { cwd, encoding: 'utf-8', timeout: 5000 });
      
      if (statusOutput.trim()) {
        lines.push('```');
        lines.push(statusOutput.trim());
        lines.push('```\n');
        
        if (diffStatOutput.trim()) {
          lines.push('**Changes:**');
          lines.push('```');
          lines.push(diffStatOutput.trim());
          lines.push('```');
        }
      } else {
        lines.push('*Working directory clean*');
      }
    } catch (gitErr: any) {
      lines.push(`*Git status unavailable: ${gitErr.message || 'Unknown error'}*`);
    }

    return lines.join('\n');
  } catch (error: any) {
    log('error', 'Snapshot failed', { error: error.message });
    return `## Error\n\nFailed to generate snapshot: ${error.message}\n\nMake sure the CassiCore daemon is running.`;
  }
}

/**
 * Execute an intelligence tool — routes to the appropriate formatter
 */
async function executeIntelligenceTool(toolName: string, args: any): Promise<string> {
  log('info', 'Executing intelligence tool', { tool: toolName, args });

  const formatters: Record<string, (args: any) => Promise<string>> = {
    cassi_activity: formatActivity,
    cassi_dialectic: formatDialectic,
    cassi_thinker: formatThinker,
    cassi_subconscious: formatSubconscious,
    cassi_consciousness: formatConsciousness,
    cassi_trace: formatTrace,
    cassi_effectiveness: formatEffectiveness,
    cassi_budget: formatBudget,
    cassi_evolution: formatEvolution,
    cassi_blindspots: formatBlindspots,
    cassi_snapshot: formatSnapshot,
  };

  const formatter = formatters[toolName];
  if (!formatter) {
    throw new Error(`Unknown intelligence tool: ${toolName}`);
  }

  try {
    return await formatter(args);
  } catch (error: any) {
    log('error', 'Intelligence tool failed', { tool: toolName, error: error.message });
    return `## Error\n\nFailed to execute ${toolName}: ${error.message}\n\nMake sure the CassiCore daemon is running.`;
  }
}

/**
 * Create MCP Server
 */
function createServer() {
  const server = new Server(
    {
      name: 'cassicore-gateway',
      version: GATEWAY_VERSION,
    },
    {
      capabilities: {
        tools: {},
        resources: {},
      },
    }
  );

  // List available tools
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: [...CASSICORE_TOOLS, ...INTELLIGENCE_TOOLS, ...MEMORY_TOOLS, ...PROVIDER_TOOLS, ...CONFIG_TOOLS, ...SESSION_TOOLS, ...ACTION_TOOLS, ...TEAM_TOOLS, ...TEAM_AGENT_TOOLS],
    };
  });

  // Handle tool calls
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    
    log('info', 'Tool call received', { tool: name, args });
    
    try {
      let result;
      
      // Extended tools (memory, providers, config, sessions, actions, teams)
      const extendedTools = new Set([
        'cassi_memory_store', 'cassi_memory_search', 'cassi_memory_recent',
        'cassi_memory_delete', 'cassi_memory_kv_get', 'cassi_memory_kv_set', 'cassi_memory_kv_del',
        'cassi_memory_stats',
        'cassi_archive_search', 'cassi_archive_get', 'cassi_archive_related', 'cassi_archive_recent',
        'cassi_browse',
        'cassi_universal_search', 'cassi_session_conversation', 'cassi_session_export',
        'cassi_resolve_ref', 'cassi_index_search', 'cassi_index_session', 'cassi_index_stats',
        'cassi_providers', 'cassi_provider_metrics', 'cassi_provider_config',
        'cassi_config_get', 'cassi_config_set',
        'cassi_sessions', 'cassi_session_detail', 'cassi_session_prune',
        'cassi_think_now', 'cassi_strategy_update', 'cassi_anomaly_ack',
        'cassi_team',
      ]);

      // C3: Agent-level team coordination tools
      const teamAgentTools = new Set([
        'cassi_team_agent_status', 'cassi_team_agent_message', 'cassi_team_agent_result',
        'cassi_team_agent_list', 'cassi_team_agent_update_plan',
        'cassi_team_agent_complete_goal', 'cassi_team_agent_goal_tree',
      ]);
      
      if (teamAgentTools.has(name)) {
        result = await executeTeamAgentTool(name, args);
      } else if (extendedTools.has(name)) {
        // Extended tools return JSON
        result = await executeExtendedTool(name, args);
      } else if (name.startsWith('cassi_')) {
        // Intelligence introspection tools return markdown directly
        const markdown = await executeIntelligenceTool(name, args);
        return {
          content: [
            {
              type: 'text',
              text: markdown,
            },
          ],
        };
      } else {
        result = await executeCassiCoreTool(name, args);
      }

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(result, null, 2),
          },
        ],
      };
    } catch (error: any) {
      log('error', 'Tool execution failed', { tool: name, error: error.message });
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({ error: error.message }, null, 2),
          },
        ],
        isError: true,
      };
    }
  });

  // List resources (files/directories accessible)
  server.setRequestHandler(ListResourcesRequestSchema, async () => {
    return {
      resources: [
        {
          uri: 'cassicore://health',
          name: 'CassiCore Health Status',
          mimeType: 'application/json',
          description: 'Current health and status of CassiCore daemon',
        },
      ],
    };
  });

  // Read resources
  server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const { uri } = request.params;
    
    if (uri === 'cassicore://health') {
      try {
        const response = await fetchWithTimeout(`${CASSICORE_URL}/health`);
        const health = await response.json();
        return {
          contents: [
            {
              uri,
              mimeType: 'application/json',
              text: JSON.stringify(health, null, 2),
            },
          ],
        };
      } catch (error: any) {
        return {
          contents: [
            {
              uri,
              mimeType: 'application/json',
              text: JSON.stringify({ status: 'error', error: error.message }),
            },
          ],
        };
      }
    }
    
    throw new Error(`Unknown resource: ${uri}`);
  });

  return server;
}

/**
 * Start with stdio transport (default for MCP)
 */
async function startStdio() {
  log('info', 'Starting CassiCore MCP Gateway (stdio mode)', { url: CASSICORE_URL });
  
  const server = createServer();
  const transport = new StdioServerTransport();
  
  await server.connect(transport);
  
  log('info', 'CassiCore MCP Gateway connected and ready');
}

/**
 * Start with HTTP/SSE transport (for remote connections)
 */
async function startHttp(port: number) {
  log('info', 'Starting CassiCore MCP Gateway (HTTP mode)', { port, url: CASSICORE_URL });
  
  const server = createServer();
  
  // Create HTTP server for SSE transport
  const httpServer = http.createServer(async (req, res) => {
    const url = new URL(req.url || '/', `http://localhost:${port}`);
    
    // Health endpoint
    if (url.pathname === '/health') {
      try {
        const cassiHealth = await fetchWithTimeout(`${CASSICORE_URL}/health`);
        const cassiStatus = await cassiHealth.json();
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'ok',
          gateway: 'cassicore-mcp-gateway',
          version: GATEWAY_VERSION,
          cassicore: cassiStatus,
        }));
      } catch (error: any) {
        res.writeHead(503, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'error',
          error: error.message,
        }));
      }
      return;
    }
    
    // Tools endpoint (REST API)
    if (url.pathname === '/tools' && req.method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify([...CASSICORE_TOOLS, ...INTELLIGENCE_TOOLS, ...MEMORY_TOOLS, ...PROVIDER_TOOLS, ...CONFIG_TOOLS, ...SESSION_TOOLS, ...ACTION_TOOLS, ...TEAM_TOOLS, ...TEAM_AGENT_TOOLS]));
      return;
    }
    
    // Execute endpoint (REST API)
    if (url.pathname === '/tools/execute' && req.method === 'POST') {
      let body = '';
      req.on('data', chunk => body += chunk);
      req.on('end', async () => {
        try {
          const { tool, args } = JSON.parse(body);
          const result = await executeCassiCoreTool(tool, args);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(result));
        } catch (error: any) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: error.message }));
        }
      });
      return;
    }
    
    res.writeHead(404);
    res.end('Not found');
  });
  
  httpServer.listen(port, () => {
    log('info', `HTTP server listening on port ${port}`);
  });
}

/**
 * Main entry point
 */
async function main() {
  const args = process.argv.slice(2);
  const httpMode = args.includes('--http');
  const portArg = args.find(arg => arg.startsWith('--port='));
  const port = portArg ? parseInt(portArg.split('=')[1], 10) : 3000;
  
  // Validate CassiCore connection
  try {
    const healthCheck = await fetchWithTimeout(`${CASSICORE_URL}/health`);
    if (!healthCheck.ok) {
      throw new Error('CassiCore health check failed');
    }
    log('info', 'CassiCore daemon connection verified');
  } catch (error: any) {
    log('error', 'Failed to connect to CassiCore daemon', { 
      url: CASSICORE_URL, 
      error: error.message 
    });
    log('warn', 'Make sure CassiCore is running: cassicore daemon');
    // Continue anyway - connection might succeed later
  }
  
  if (httpMode) {
    await startHttp(port);
  } else {
    await startStdio();
  }
}

main().catch((error) => {
  log('error', 'Gateway failed to start', { error: error.message });
  process.exit(1);
});
