import type { ToolDefinition, ToolHandler } from '../types.js'
import type { GraphAttnPropagator } from '../../intelligence/mnemic-field/graph-attn-propagator.js'

export interface GraphDiscoverDeps {
  getPropagator: () => GraphAttnPropagator | undefined
  getBranchEngramIds: () => Map<string, string>
  getBranchGoals: () => Map<string, string>
}

let _deps: GraphDiscoverDeps | undefined

export function setGraphDiscoverDeps(deps: GraphDiscoverDeps | undefined): void {
  _deps = deps
}

export const graphDiscoverDefinition: ToolDefinition = {
  name: 'graph_discover',
  description:
    'Query the MnemicField knowledge graph for sibling discoveries relevant to ' +
    'the current constellation. Walks typed edges (spawned_from, part_of, similar_to, ' +
    'temporal_neighbor) from all active branch engrams and returns the most charged ' +
    'findings. Returns structured context about what other branches are finding.',
  parameters: {
    type: 'object',
    properties: {
      edgeTypes: {
        type: 'array',
        items: { type: 'string' },
        description: 'Edge types to traverse. Default: ["spawned_from", "part_of", "similar_to", "temporal_neighbor"]',
      },
      maxHops: {
        type: 'number',
        description: 'Max BFS hops from seeds. Default: 2. Higher values find more distant connections but are slower.',
      },
      topN: {
        type: 'number',
        description: 'Max results to return. Default: 5.',
      },
      minCharge: {
        type: 'number',
        description: 'Minimum relevance charge (0-1). Default: 0.02. Higher = more relevant but fewer results.',
      },
    },
  },
  timeoutMs: 15_000,
  category: 'cognitive',
  requiredPermission: 'read-only',
}

export const graphDiscoverHandler: ToolHandler = async (input) => {
  const deps = _deps
  if (!deps) {
    return 'No constellation session active. The graph_discover tool is only available during constellation runs.'
  }

  const propagator = deps.getPropagator()
  if (!propagator) {
    return 'MnemicField graph not available for this session.'
  }

  const branchEngramIds = deps.getBranchEngramIds()
  if (branchEngramIds.size === 0) {
    return 'No active branches in current constellation.'
  }

  const seedIds = [...branchEngramIds.values()]

  const edgeTypes = input.edgeTypes as string[] | undefined
  const maxHops = input.maxHops as number | undefined
  const topN = input.topN as number | undefined
  const minCharge = input.minCharge as number | undefined

  try {
    const results = propagator.propagate({
      seedIds,
      edgeTypes: edgeTypes as any,
      maxHops: maxHops ?? 2,
      topN: topN ?? 5,
      minCharge: minCharge ?? 0.02,
      hopDecay: 0.6,
      maxFrontierSize: 800,
    })

    if (results.length === 0) {
      return 'No sibling discoveries found via graph propagation.'
    }

    const branchGoals = deps.getBranchGoals()
    const grouped = new Map<string, typeof results>()

    for (const r of results) {
      if (branchEngramIds.has(r.engram.id)) continue
      const src = findSourceBranch(r, branchEngramIds)
      const key = src ?? 'unknown'
      const list = grouped.get(key) ?? []
      list.push(r)
      grouped.set(key, list)
    }

    const lines: string[] = [
      `Graph Discover — ${results.length} engrams from ${grouped.size} sources`,
      '',
    ]

    for (const [src, entries] of grouped) {
      const goal = branchGoals.get(src) ?? ''
      const goalPreview = goal ? ` (${goal.slice(0, 80)})` : ''
      lines.push(`Branch ${src.slice(-12)}${goalPreview}:`)
      for (const e of entries) {
        const chargeStr = (e.charge * 100).toFixed(0)
        const preview = truncate(e.engram.content, 160)
        const typeTag = e.engram.nodeType ?? 'fact'
        const edgeStr = e.paths[0]
          ? ` via ${e.paths[0].hops.map(h => h.edgeType).join('→')}`
          : ''
        lines.push(`  [${chargeStr}%] ${typeTag}${edgeStr}`)
        lines.push(`    ${preview}`)
      }
      lines.push('')
    }

    return lines.join('\n')
  } catch (err) {
    return `Graph discovery failed: ${String(err)}`
  }
}

function findSourceBranch(
  result: { engram: { id: string }; paths: Array<{ hops: Array<{ direction: string; engramId: string }> }> },
  branchEngramIds: Map<string, string>,
): string | undefined {
  for (const path of result.paths) {
    for (const hop of path.hops) {
      for (const [helixId, eid] of branchEngramIds) {
        if (hop.engramId === eid) return helixId
      }
    }
  }
  return undefined
}

function truncate(s: string, maxLen: number): string {
  if (s.length <= maxLen) return s
  return s.slice(0, maxLen - 1) + '…'
}
