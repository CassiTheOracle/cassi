#!/usr/bin/env node
/**
 * Memory Tools Module
 * Memory store, KV store, archive, and search operations
 */

import { fetchWithTimeout } from './helpers.js';
import type { ILogger } from '../../types/interfaces.js';

/**
 * Tool definitions for memory tools
 */
export const MEMORY_TOOLS = [
  {
    name: 'memory_store',
    description: "Store a memory in CassiCore's persistent memory system. Memories persist across sessions and can be searched later.",
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
    name: 'memory_search',
    description: "Search CassiCore's persistent memory using full-text search. Returns matching memories with relevance scores.",
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
    name: 'memory_recent',
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
    name: 'memory_delete',
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
    name: 'memory_kv_get',
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
    name: 'memory_kv_set',
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
    name: 'memory_kv_del',
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
    name: 'memory_stats',
    description: 'Get memory system statistics — entry counts by type, archive stats, and queue depth.',
    inputSchema: { type: 'object', properties: {} },
  },
  {
    name: 'archive_search',
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
    name: 'archive_get',
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
    name: 'archive_related',
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
    name: 'archive_recent',
    description: 'List the most recently archived entries across all types (conversations, insights, patterns, etc.).',
    inputSchema: {
      type: 'object',
      properties: {
        limit: { type: 'number', description: 'Max results (default 10)' },
      },
    },
  },
  {
    name: 'browse',
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
    name: 'universal_search',
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
];

/**
 * Memory tool names set for quick lookup
 */
export const MEMORY_TOOL_NAMES = new Set(MEMORY_TOOLS.map(t => t.name));

/**
 * Execute a memory tool
 */
export async function executeMemoryTool(
  baseUrl: string,
  toolName: string,
  args: any,
  logger: ILogger
): Promise<any> {
  logger.info('Executing memory tool', { tool: toolName, args });

  switch (toolName) {
    case 'memory_store': {
      const res = await fetchWithTimeout(`${baseUrl}/memory/store`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: args.key, content: args.content, tags: args.tags }),
      });
      if (!res.ok) throw new Error(`Memory store failed: ${await res.text()}`);
      return await res.json();
    }

    case 'memory_search': {
      const params = new URLSearchParams({ query: args.query });
      if (args.limit) params.set('limit', String(args.limit));
      const res = await fetchWithTimeout(`${baseUrl}/memory/search?${params}`);
      if (!res.ok) throw new Error(`Memory search failed: ${await res.text()}`);
      return await res.json();
    }

    case 'memory_recent': {
      const params = new URLSearchParams();
      if (args?.limit) params.set('limit', String(args.limit));
      const qs = params.toString();
      const res = await fetchWithTimeout(`${baseUrl}/memory/recent${qs ? '?' + qs : ''}`);
      if (!res.ok) throw new Error(`Memory recent failed: ${await res.text()}`);
      return await res.json();
    }

    case 'memory_delete': {
      const res = await fetchWithTimeout(`${baseUrl}/memory/${encodeURIComponent(args.id)}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`Memory delete failed: ${await res.text()}`);
      return await res.json();
    }

    case 'memory_kv_get': {
      const res = await fetchWithTimeout(`${baseUrl}/memory/kv/${encodeURIComponent(args.key)}`);
      if (!res.ok) throw new Error(`KV get failed: ${await res.text()}`);
      return await res.json();
    }

    case 'memory_kv_set': {
      const res = await fetchWithTimeout(`${baseUrl}/memory/kv`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: args.key, value: args.value }),
      });
      if (!res.ok) throw new Error(`KV set failed: ${await res.text()}`);
      return await res.json();
    }

    case 'memory_kv_del': {
      const res = await fetchWithTimeout(`${baseUrl}/memory/kv/${encodeURIComponent(args.key)}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`KV delete failed: ${await res.text()}`);
      return await res.json();
    }

    case 'memory_stats': {
      const res = await fetchWithTimeout(`${baseUrl}/memory/stats`);
      if (!res.ok) throw new Error(`Memory stats failed: ${await res.text()}`);
      return await res.json();
    }

    case 'archive_search': {
      const res = await fetchWithTimeout(`${baseUrl}/memory/archives/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: args.query, limit: args.limit, sortBy: args.sortBy, filters: args.filters }),
      });
      if (!res.ok) throw new Error(`Archive search failed: ${await res.text()}`);
      return await res.json();
    }

    case 'archive_get': {
      const res = await fetchWithTimeout(`${baseUrl}/memory/archives/${encodeURIComponent(args.id)}`);
      if (!res.ok) throw new Error(`Archive get failed: ${await res.text()}`);
      return await res.json();
    }

    case 'archive_related': {
      const params = new URLSearchParams();
      if (args.limit) params.set('limit', String(args.limit));
      const qs = params.toString();
      const res = await fetchWithTimeout(`${baseUrl}/memory/archives/${encodeURIComponent(args.id)}/related${qs ? '?' + qs : ''}`);
      if (!res.ok) throw new Error(`Archive related failed: ${await res.text()}`);
      return await res.json();
    }

    case 'archive_recent': {
      const params = new URLSearchParams();
      if (args?.limit) params.set('limit', String(args.limit));
      const qs = params.toString();
      const res = await fetchWithTimeout(`${baseUrl}/memory/archives/recent${qs ? '?' + qs : ''}`);
      if (!res.ok) throw new Error(`Archive recent failed: ${await res.text()}`);
      return await res.json();
    }

    case 'browse': {
      const params = new URLSearchParams({ category: args.category });
      if (args.minCount) params.set('minCount', String(args.minCount));
      const res = await fetchWithTimeout(`${baseUrl}/memory/archives/browse?${params}`);
      if (!res.ok) throw new Error(`Browse failed: ${await res.text()}`);
      return await res.json();
    }

    case 'universal_search': {
      const res = await fetchWithTimeout(`${baseUrl}/memory/universal-search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: args.query, includeMemories: args.includeMemories, includeArchives: args.includeArchives, limit: args.limit }),
      });
      if (!res.ok) throw new Error(`Universal search failed: ${await res.text()}`);
      return await res.json();
    }

    case 'memory_invalidate': {
      const res = await fetchWithTimeout(`${baseUrl}/memory/${encodeURIComponent(args.id)}/invalidate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: args.reason }),
      });
      if (!res.ok) throw new Error(`Memory invalidate failed: ${await res.text()}`);
      return await res.json();
    }

    case 'memory_supersede': {
      const res = await fetchWithTimeout(`${baseUrl}/memory/${encodeURIComponent(args.oldId || args.id)}/supersede`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: args.content, metadata: args.metadata }),
      });
      if (!res.ok) throw new Error(`Memory supersede failed: ${await res.text()}`);
      return await res.json();
    }

    default:
      throw new Error(`Unknown memory tool: ${toolName}`);
  }
}

/**
 * Get all memory tool definitions
 * @dep callers: getAllTools (mcp/cassicore-gateway.ts)
 * @dep flows: CreateHierarchyBridge → GetMemoryTools (4/4)
 * @dep module: Gateway
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */
export function getMemoryTools(): Array<{
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}> {
  return MEMORY_TOOLS;
}
