#!/usr/bin/env node
/**
 * self-model-tools.ts — MCP gateway tool for Self-Model Field operations.
 *
 * Exposes architectural self-knowledge operations: retrieve, store, update,
 * cross-retrieve, list modules, find weaknesses, and view stats.
 *
 * This tool lets the agent interact with its own architectural understanding —
 * querying what modules exist, adding new knowledge (patterns, principles,
 * weaknesses), updating descriptions, and bridging to episodic memory.
 */

import { fetchWithTimeout } from './helpers.js'
import type { ILogger } from '../../types/interfaces.js'

export const SELF_MODEL_TOOL_NAME = 'self_model'

export const SELF_MODEL_TOOL = {
  name: SELF_MODEL_TOOL_NAME,
  description:
    'Self-Model Field operations — query, store, and update architectural self-knowledge. ' +
    'The self-model stores semantic understanding of the codebase architecture ' +
    '(modules, capabilities, patterns, principles, weaknesses, evolution). ' +
    'Use this to understand your own architecture, store new insights, or bridge to episodic memory.\n\n' +
    'Common actions: retrieve (find architecture knowledge by concept), ' +
    'cross_retrieve (blend architecture + episodic memory), ' +
    'store (add new knowledge), update (modify existing engram), ' +
    'modules (list architectural modules), stats (field overview).',
  inputSchema: {
    type: 'object' as const,
    properties: {
      action: {
        type: 'string',
        enum: [
          'retrieve', 'cross_retrieve', 'store', 'update',
          'modules', 'weaknesses', 'dependency_graph',
          'stats', 'portals', 'ingest',
        ],
        description:
          'Operation to perform on the self-model field.',
      },
      query: {
        type: 'string',
        description: 'Search query (for retrieve, cross_retrieve actions).',
      },
      limit: {
        type: 'number',
        description: 'Maximum results to return (default varies by action).',
      },
      prefer: {
        type: 'string',
        enum: ['episodic', 'self-model'],
        description: 'Preferred field for cross_retrieve (default: no preference).',
      },
      nodeType: {
        type: 'string',
        enum: ['module', 'capability', 'pattern', 'principle', 'weakness', 'evolution'],
        description: 'Engram type (for store action).',
      },
      name: {
        type: 'string',
        description: 'Name of the engram (for store action).',
      },
      description: {
        type: 'string',
        description: 'Description content (for store action).',
      },
      metadata: {
        type: 'object',
        description: 'Additional metadata (for store action).',
      },
      tags: {
        type: 'array',
        items: { type: 'string' },
        description: 'Tags for categorization (for store action).',
      },
      id: {
        type: 'string',
        description: 'Engram ID (for update action).',
      },
      content: {
        type: 'string',
        description: 'New content (for update action).',
      },
      domain: {
        type: 'string',
        description: 'Filter by domain (for modules action).',
      },
      severity: {
        type: 'string',
        enum: ['low', 'medium', 'high', 'critical'],
        description: 'Filter by severity (for weaknesses action).',
      },
      updateExisting: {
        type: 'boolean',
        description: 'Update existing descriptions during ingest (default true).',
      },
    },
    required: ['action'],
  },
}

export function getSelfModelTool(): typeof SELF_MODEL_TOOL {
  return SELF_MODEL_TOOL
}

export async function executeSelfModelTool(
  baseUrl: string,
  args: Record<string, unknown>,
  logger: ILogger,
): Promise<unknown> {
  const action = args.action as string
  if (!action) throw new Error('Missing required parameter: action')

  const api = `${baseUrl}/memory/self-model`

  logger.info('Executing self-model tool', { action })

  switch (action) {
    case 'retrieve': {
      const query = args.query as string
      if (!query) throw new Error('retrieve requires a query parameter')
      const limit = (args.limit as number) ?? 10
      const res = await fetchWithTimeout(
        `${api}/retrieve?query=${encodeURIComponent(query)}&limit=${limit}`,
      )
      return res.json()
    }

    case 'cross_retrieve': {
      const query = args.query as string
      if (!query) throw new Error('cross_retrieve requires a query parameter')
      const limit = (args.limit as number) ?? 12
      const prefer = args.prefer as string | undefined
      let url = `${api}/cross-retrieve?query=${encodeURIComponent(query)}&limit=${limit}`
      if (prefer) url += `&prefer=${prefer}`
      const res = await fetchWithTimeout(url)
      return res.json()
    }

    case 'store': {
      const nodeType = args.nodeType as string
      if (!nodeType) throw new Error('store requires nodeType')
      const name = args.name as string
      if (!name) throw new Error('store requires name')
      const description = (args.description as string) ?? ''
      const metadata = (args.metadata as Record<string, unknown>) ?? {}
      const tags = (args.tags as string[]) ?? []

      const res = await fetchWithTimeout(`${api}/store`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodeType, name, description, metadata, tags }),
      })
      return res.json()
    }

    case 'update': {
      const id = args.id as string
      if (!id) throw new Error('update requires id')
      const content = args.content as string | undefined
      const metadata = args.metadata as Record<string, unknown> | undefined
      const tags = args.tags as string[] | undefined

      const res = await fetchWithTimeout(`${api}/update`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, content, metadata, tags }),
      })
      return res.json()
    }

    case 'modules': {
      const domain = args.domain as string | undefined
      const limit = (args.limit as number) ?? 50
      let url = `${api}/modules?limit=${limit}`
      if (domain) url += `&domain=${encodeURIComponent(domain)}`
      const res = await fetchWithTimeout(url)
      return res.json()
    }

    case 'weaknesses': {
      const severity = args.severity as string | undefined
      const limit = (args.limit as number) ?? 50
      let url = `${api}/weaknesses?limit=${limit}`
      if (severity) url += `&severity=${severity}`
      const res = await fetchWithTimeout(url)
      return res.json()
    }

    case 'dependency_graph': {
      const res = await fetchWithTimeout(`${api}/dependency-graph`)
      return res.json()
    }

    case 'stats': {
      const res = await fetchWithTimeout(`${api}/stats`)
      return res.json()
    }

    case 'portals': {
      const res = await fetchWithTimeout(`${api}/portals`)
      return res.json()
    }

    case 'ingest': {
      const updateExisting = (args.updateExisting as boolean) ?? true
      const res = await fetchWithTimeout(`${api}/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updateExisting }),
      })
      return res.json()
    }

    default:
      throw new Error(`Unknown self-model action: ${action}`)
  }
}
