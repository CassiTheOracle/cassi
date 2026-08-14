#!/usr/bin/env node
/**
 * Knowledge Tools Module
 *
 * MCP tools for accessing the Knowledge Field — research papers, techniques,
 * and findings. Implements the Paper Lantern pattern:
 * - knowledge_explore: Find relevant techniques for a problem
 * - knowledge_deep_dive: Get full details on a technique
 * - knowledge_compare: Side-by-side technique comparison
 */

import { fetchWithTimeout } from './helpers.js'
import type { ILogger } from '@cassicore/foundation'

export const KNOWLEDGE_TOOL_NAME = 'knowledge'

export const KNOWLEDGE_TOOL = {
  name: KNOWLEDGE_TOOL_NAME,
  description: 'Knowledge Field operations — explore research, deep-dive techniques, and compare approaches. Use action parameter to select operation.\n\nUse this tool when you need external research knowledge: papers, algorithms, techniques, benchmarks. The knowledge field uses topology-aware retrieval (kindling) to find related approaches.\n\nCommon actions: explore (find techniques for a problem), deep_dive (full technique details), compare (side-by-side comparison), retrieve (search by query).',
  inputSchema: {
    type: 'object' as const,
    properties: {
      action: {
        type: 'string',
        enum: ['explore', 'deep_dive', 'compare', 'retrieve', 'stats', 'ingest'],
        description: 'Knowledge operation to perform',
      },
      // explore params
      problem: {
        type: 'string',
        description: 'Description of the problem to find techniques for (for explore action)',
      },
      domain: {
        type: 'string',
        description: 'Filter by domain (e.g. "testing", "retrieval", "optimization")',
      },
      // deep_dive params
      technique_id: {
        type: 'string',
        description: 'Engram ID of the technique to explore (for deep_dive action)',
      },
      // compare params
      idA: {
        type: 'string',
        description: 'First technique ID (for compare action)',
      },
      idB: {
        type: 'string',
        description: 'Second technique ID (for compare action)',
      },
      // retrieve params
      query: {
        type: 'string',
        description: 'Search query (for retrieve action)',
      },
      // common
      limit: {
        type: 'number',
        description: 'Maximum results to return (default 10)',
      },
      // ingest params
      dir: {
        type: 'string',
        description: 'Directory containing JSON paper files (for ingest action)',
      },
    },
    required: ['action'],
  },
}

export function getKnowledgeTool(): typeof KNOWLEDGE_TOOL {
  return KNOWLEDGE_TOOL
}

export async function executeKnowledgeTool(
  baseUrl: string,
  args: Record<string, unknown>,
  logger: ILogger,
): Promise<unknown> {
  const action = args.action as string
  if (!action) throw new Error('Missing required parameter: action')

  const api = `${baseUrl}/memory/knowledge`
  logger.info('Executing knowledge tool', { action })

  switch (action) {
    case 'explore': {
      const problem = args.problem as string
      if (!problem) throw new Error('explore requires a problem parameter')
      const limit = (args.limit as number) ?? 5
      const domain = args.domain as string | undefined
      const query = domain ? `${problem} ${domain}` : problem
      const res = await fetchWithTimeout(
        `${api}/retrieve?query=${encodeURIComponent(query)}&limit=${limit}`,
      )
      return res.json()
    }

    case 'deep_dive': {
      const techniqueId = args.technique_id as string
      if (!techniqueId) throw new Error('deep_dive requires a technique_id parameter')
      // Retrieve the specific engram and its neighbors by ID
      const res = await fetchWithTimeout(`${api}/item/${encodeURIComponent(techniqueId)}`)
      const result = await res.json() as any
      if (!result.ok || !result.engram) {
        throw new Error(`Technique not found: ${techniqueId}`)
      }
      return result
    }

    case 'compare': {
      const idA = args.idA as string
      const idB = args.idB as string
      if (!idA || !idB) throw new Error('compare requires idA and idB parameters')
      const res = await fetchWithTimeout(`${api}/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idA, idB }),
      })
      return res.json()
    }

    case 'retrieve': {
      const query = args.query as string
      if (!query) throw new Error('retrieve requires a query parameter')
      const limit = (args.limit as number) ?? 10
      const res = await fetchWithTimeout(
        `${api}/retrieve?query=${encodeURIComponent(query)}&limit=${limit}`,
      )
      return res.json()
    }

    case 'stats': {
      const res = await fetchWithTimeout(`${api}/stats`)
      return res.json()
    }

    case 'ingest': {
      const dir = args.dir as string
      if (!dir) throw new Error('ingest requires a dir parameter')
      const res = await fetchWithTimeout(`${api}/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dir }),
      })
      return res.json()
    }

    default:
      throw new Error(`Unknown knowledge action: ${action}`)
  }
}
