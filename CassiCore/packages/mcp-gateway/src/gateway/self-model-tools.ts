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
import type { ILogger } from '@cassicore/foundation'

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
    'link (create a synapse between two engrams), ' +
    'modules (list architectural modules), stats (field overview).',
  inputSchema: {
    type: 'object' as const,
    properties: {
      action: {
        type: 'string',
        enum: [
          'retrieve', 'cross_retrieve', 'store', 'update', 'link',
          'modules', 'weaknesses', 'dependency_graph',
          'stats', 'portals', 'ingest',
          'reclassify', 'validate_annotations', 'audit_coverage',
          'wire_capabilities', 'embed_flows', 'purge_deprecated',
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
      sourceId: {
        type: 'string',
        description: 'Source engram ID (for link action).',
      },
      targetId: {
        type: 'string',
        description: 'Target engram ID (for link action).',
      },
      edgeType: {
        type: 'string',
        description: 'Edge type for link action (e.g., \"implements\", \"depends_on\", \"supports\"). Default: \"implements\".',
      },
      edgeWeight: {
        type: 'number',
        description: 'Optional synapse weight (0-1, default 1.0).',
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

    case 'link': {
      if (!args?.sourceId || !args?.targetId) {
        throw new Error('sourceId and targetId are required for link action')
      }
      const body: Record<string, unknown> = {
        sourceId: args.sourceId,
        targetId: args.targetId,
        edgeType: args.edgeType || 'implements',
      }
      if (args.edgeWeight !== undefined) body.edgeWeight = args.edgeWeight
      if (args.metadata !== undefined) body.metadata = args.metadata

      const res = await fetchWithTimeout(`${api}/link`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
        throw new Error(`Link failed: ${(err as any).error || res.status}`)
      }
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

    case 'reclassify': {
      const body: Record<string, unknown> = {}
      if (args.domain !== undefined) body.domain = args.domain
      if (args.threshold !== undefined) body.threshold = args.threshold
      body.dryRun = args.dryRun !== false  // default true for safety
      const res = await fetchWithTimeout(`${api}/reclassify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      return res.json()
    }

    case 'validate_annotations': {
      const res = await fetchWithTimeout(`${api}/validate-annotations`)
      return res.json()
    }

    case 'audit_coverage': {
      const res = await fetchWithTimeout(`${api}/audit-coverage`)
      return res.json()
    }

    case 'wire_capabilities': {
      const dryRun = args.dryRun !== false
      const res = await fetchWithTimeout(`${api}/wire-capabilities`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dryRun }),
      })
      return res.json()
    }

    case 'embed_flows': {
      const dryRun = args.dryRun !== false
      const res = await fetchWithTimeout(`${api}/embed-flows`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dryRun }),
      })
      return res.json()
    }

    case 'purge_deprecated': {
      const body: Record<string, unknown> = {}
      if (args.modules !== undefined) body.modules = args.modules
      body.dryRun = args.dryRun !== false
      const res = await fetchWithTimeout(`${api}/purge-deprecated`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      return res.json()
    }

    default:
      throw new Error(`Unknown self-model action: ${action}`)
  }
}
