import { fetchJson } from '../helpers.js'
import type { ToolDefinition, ToolHandler } from '../types.js'

export const COGNITIVE_TOOLS: ToolDefinition[] = [
  {
    name: 'cognitive_enrich',
    description: 'At task start or when context feels stale: pulls CassiCore\'s full intelligence layer -- active thinker thoughts, dialectic insights, cross-session patterns from MnemicField, anomaly detector findings, and team status. Returns structured context so you know what CassiCore is thinking about before you decide what to do.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'Optional session ID to scope enrichment. Omit for global enrichment.' },
        includeThinker: { type: 'boolean', description: 'Include active thinker activity. Default: true.' },
        includeDialectic: { type: 'boolean', description: 'Include dialectic cross-examination insights. Default: true.' },
        includeAnomalies: { type: 'boolean', description: 'Include anomaly detector findings. Default: true.' },
        includeTeams: { type: 'boolean', description: 'Include active Constellation/Helix team status. Default: true.' },
      },
    },
  },
  {
    name: 'memory_retrieve',
    description: 'Before making a decision: search CassiCore\'s MnemicField for what you learned in past sessions. Uses semantic vector search to find related facts, decisions, and patterns so you build on prior work instead of rediscovering it.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Natural language query for what to find.' },
        limit: { type: 'number', description: 'Max results. Default: 5.' },
        nodeType: { type: 'string', enum: ['fact', 'decision', 'insight', 'goal', 'anomaly', 'concern', 'episode'], description: 'Filter by memory type. Omit for all types.' },
      },
      required: ['query'],
    },
  },
  {
    name: 'memory_store',
    description: 'After an important discovery or decision: persist it to CassiCore\'s MnemicField so future sessions can find it. Tagged memories survive session boundaries and power cross-session recall.',
    inputSchema: {
      type: 'object',
      properties: {
        content: { type: 'string', description: 'What to remember (fact, decision, insight).' },
        nodeType: { type: 'string', enum: ['fact', 'decision', 'insight', 'goal', 'anomaly', 'concern', 'episode'], description: 'Type of memory. Default: fact.' },
        tags: { type: 'array', items: { type: 'string' }, description: 'Tags for categorization and retrieval.' },
      },
      required: ['content'],
    },
  },
  {
    name: 'memory_graph',
    description: 'Explore how memories connect. Starting from a known engram, traverse its synapses to find related knowledge -- reveals patterns and relationships that flat search cannot show.',
    inputSchema: {
      type: 'object',
      properties: {
        engramId: { type: 'string', description: 'Starting engram ID (from memory_retrieve results).' },
        direction: { type: 'string', enum: ['outgoing', 'incoming', 'both'], description: 'Which direction to traverse. Default: both.' },
        maxDepth: { type: 'number', description: 'Max traversal depth. Default: 2.' },
        edgeType: { type: 'string', enum: ['references', 'causes', 'contradicts', 'supports', 'refines', 'generalizes', 'specializes'], description: 'Filter by relationship type. Omit for all.' },
      },
      required: ['engramId'],
    },
  },
  {
    name: 'memory_browse',
    description: 'Browse and discover memories in CassiCore\'s MnemicField without a specific search query. Use this to explore what\'s stored: see field stats, list nuclei (clusters of related engrams), abstractions (higher-order patterns), browse by tag or type, find popular/high-potentiation engrams, explore neighborhoods around a known engram, or review tensions between contradictory memories.',
    inputSchema: {
      type: 'object',
      properties: {
        action: { type: 'string', enum: ['overview', 'nuclei', 'abstractions', 'by_tag', 'by_type', 'popular', 'neighborhood', 'tensions'], description: 'Browse action: overview (field stats), nuclei (engram clusters), abstractions (higher-order patterns), by_tag (FTS5 search on tags), by_type (list engrams of a specific node_type), popular (top by potentiation), neighborhood (graph traversal from an engram), tensions (contradictory engram pairs).' },
        query: { type: 'string', description: 'For by_tag: the tag to search. For neighborhood: the starting engram ID. For other actions: unused.' },
        nodeType: { type: 'string', enum: ['fact', 'decision', 'insight', 'goal', 'anomaly', 'concern', 'episode', 'abstraction', 'pattern'], description: 'For by_type: the node type to browse.' },
        limit: { type: 'number', description: 'Max results. Default varies by action (10-50).' },
        edgeType: { type: 'string', enum: ['references', 'causes', 'contradicts', 'supports', 'refines', 'generalizes', 'specializes'], description: 'For neighborhood: filter by relationship type.' },
        maxDepth: { type: 'number', description: 'For neighborhood: max graph traversal depth. Default: 2. Max: 5.' },
        minPotentiation: { type: 'number', description: 'For tensions: minimum potentiation threshold. Default: 0.3.' },
      },
      required: ['action'],
    },
  },
  {
    name: 'self_model',
    description: 'Understand CassiCore\'s own architecture and capabilities. Query the Self-Model Field to learn what modules exist, what patterns are established, known weaknesses, and architectural principles -- useful when deciding which CassiCore systems to leverage.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'What aspect of CassiCore to learn about (e.g., "thalamus", "memory", "constellation").' },
        limit: { type: 'number', description: 'Max results. Default: 5.' },
      },
      required: ['query'],
    },
  },
]

export async function executeCognitiveTool(
  adminUrl: string,
  name: string,
  args: any,
  _hermesDbPath: string,
  _logger: any,
): Promise<{ content: Array<{ type: 'text'; text: string }>; isError?: boolean }> {
  try {
    switch (name) {
      case 'cognitive_enrich': {
        const parts: string[] = []
        const anyIncluded = args.includeThinker !== false || args.includeDialectic !== false || args.includeAnomalies !== false || args.includeTeams !== false
        if (!anyIncluded) {
          return { content: [{ type: 'text', text: 'CassiCore enrichment available -- connected to daemon.' }] }
        }

        if (args.includeThinker !== false) {
          const thinker = await fetchJson(`${adminUrl}/intelligence/thinker`, { timeoutMs: 5000 }).catch(() => null)
          if (thinker?.activity) {
            parts.push(`<thinker>\n${JSON.stringify(thinker.activity, null, 2).slice(0, 2000)}\n</thinker>`)
          }
        }

        if (args.includeDialectic !== false) {
          const activity = await fetchJson(`${adminUrl}/intelligence/activity`, { timeoutMs: 5000 }).catch(() => null)
          if (activity?.dialectic) {
            parts.push(`<dialectic>\n${JSON.stringify(activity.dialectic, null, 2).slice(0, 2000)}\n</dialectic>`)
          }
        }

        if (args.includeAnomalies !== false) {
          const cortex = await fetchJson(`${adminUrl}/cortex/search?type=anomaly&limit=5`, { timeoutMs: 5000 }).catch(() => null)
          if (cortex?.signals?.length) {
            parts.push(`<anomalies>\n${cortex.signals.map((s: any) => `- ${(s.content ?? '').slice(0, 300)}`).join('\n')}\n</anomalies>`)
          }
        }

        if (args.includeTeams !== false) {
          const teams = await fetchJson(`${adminUrl}/teams`, { timeoutMs: 5000 }).catch(() => null)
          if (teams?.teams?.length) {
            const active = teams.teams.filter((t: any) => t.status === 'running' || t.status === 'pending')
            if (active.length > 0) {
              parts.push(`<active-teams count="${active.length}">\n${active.map((t: any) => `- ${t.id}: ${(t.goal ?? '').slice(0, 100)}`).join('\n')}\n</active-teams>`)
            }
          }
        }

        if (parts.length === 0) {
          return { content: [{ type: 'text', text: 'CassiCore enrichment available--connected to daemon, but no activity to report.' }] }
        }
        return { content: [{ type: 'text', text: parts.join('\n\n') }] }
      }

      case 'memory_retrieve': {
        const result = await fetchJson(
          `${adminUrl}/memory/universal-search?q=${encodeURIComponent(args.query)}&limit=${args.limit ?? 5}${args.nodeType ? `&node_type=${args.nodeType}` : ''}`,
          { timeoutMs: 10_000 },
        )
        const hits = result?.hits ?? []
        if (hits.length === 0) {
          return { content: [{ type: 'text', text: `No memories found for "${args.query}".` }] }
        }
        let out = `## Memory Results: "${args.query}"\n\n`
        for (const hit of hits) {
          out += `- **[${hit.nodeType ?? 'memory'}] ${hit.id}**`
          if (hit.score != null) out += ` (score: ${typeof hit.score === 'number' ? hit.score.toFixed(3) : hit.score})`
          if (hit.potentiation != null) out += ` (pot: ${typeof hit.potentiation === 'number' ? hit.potentiation.toFixed(2) : hit.potentiation})`
          if (hit.tags?.length) out += ` [${hit.tags.join(', ')}]`
          out += `: ${(hit.content ?? '').slice(0, 500).replace(/\n/g, ' ')}\n`
        }
        return { content: [{ type: 'text', text: out }] }
      }

      case 'memory_store': {
        const result = await fetchJson(`${adminUrl}/memory/store`, {
          method: 'POST',
          body: { type: args.nodeType ?? 'fact', content: args.content, metadata: { tags: args.tags ?? [], source: 'hermes-gateway' } },
          timeoutMs: 5000,
        })
        return { content: [{ type: 'text', text: `Memory stored. ID: ${result?.id ?? 'stored'}` }] }
      }

      case 'memory_graph': {
        const params = new URLSearchParams({ direction: args.direction ?? 'both' })
        if (args.edgeType) params.set('edge_type', args.edgeType)
        if (args.maxDepth) params.set('limit', String(args.maxDepth * 10))
        const result = await fetchJson(`${adminUrl}/memory/engram/${encodeURIComponent(args.engramId)}/synapses?${params.toString()}`, { timeoutMs: 10_000 })
        const synapses = result?.synapses ?? []
        if (synapses.length === 0) {
          return { content: [{ type: 'text', text: `No synapses found for engram ${args.engramId}.` }] }
        }
        let out = `## Graph: Synapses of ${args.engramId}\n\n`
        for (const s of synapses) {
          out += `- **${s.edgeType}**: ${s.targetName ?? s.targetId ?? '?'} (${s.confidence ?? '?'} confidence)\n`
        }
        return { content: [{ type: 'text', text: out }] }
      }

      case 'memory_browse': {
        const action: string = args.action ?? 'overview'
        const limit = args.limit ?? 20

        switch (action) {
          case 'overview': {
            const result = await fetchJson(`${adminUrl}/memory/stats`, { timeoutMs: 5000 })
            const s = result?.stats ?? result ?? {}
            return { content: [{ type: 'text', text: `## MnemicField Overview

- Engrams: ${s.engramCount ?? '?'}
- Synapses: ${s.synapseCount ?? '?'}
- Nuclei: ${s.nucleusCount ?? '?'}
- Spikes: ${s.spikeCount ?? '?'}
- Avg Potentiation: ${typeof s.avgPotentiation === 'number' ? s.avgPotentiation.toFixed(3) : '?'}
${s.topEngramsByPotentiation?.length ? `\n### Top Engrams by Potentiation\n${s.topEngramsByPotentiation.map((e: any) => `- **[${e.id}]** (pot: ${typeof e.potentiation === 'number' ? e.potentiation.toFixed(3) : e.potentiation}): ${(e.content ?? '').slice(0, 120)}`).join('\n')}` : ''}` }] }
          }

          case 'nuclei': {
            const result = await fetchJson(`${adminUrl}/memory/nuclei`, { timeoutMs: 5000 })
            const nuclei = result?.nuclei ?? []
            if (nuclei.length === 0) return { content: [{ type: 'text', text: 'No nuclei found.' }] }
            let out = `## Nuclei (${nuclei.length})\n\n`
            for (const n of nuclei) {
              out += `- **${n.id ?? '?'}**: ${n.label ?? n.name ?? ''}`
              if (n.avg_potentiation != null) out += ` (avg pot: ${Number(n.avg_potentiation).toFixed(3)})`
              if (n.member_count != null) out += ` (members: ${n.member_count})`
              out += '\n'
            }
            return { content: [{ type: 'text', text: out }] }
          }

          case 'abstractions': {
            const result = await fetchJson(`${adminUrl}/memory/abstractions`, { timeoutMs: 5000 })
            const items = result?.abstractions ?? []
            if (items.length === 0) return { content: [{ type: 'text', text: 'No abstractions found.' }] }
            let out = `## Abstractions (${items.length})\n\n`
            for (const e of items) {
              out += `- **[${e.nodeType ?? 'abstraction'}] ${e.id}**`
              if (e.potentiation != null) out += ` (pot: ${typeof e.potentiation === 'number' ? e.potentiation.toFixed(2) : e.potentiation})`
              if (e.tags?.length) out += ` [${e.tags.join(', ')}]`
              out += `: ${(e.content ?? '').slice(0, 400).replace(/\n/g, ' ')}\n`
            }
            return { content: [{ type: 'text', text: out }] }
          }

          case 'by_tag': {
            if (!args.query) return { content: [{ type: 'text', text: 'query required for by_tag action.' }], isError: true }
            const result = await fetchJson(
              `${adminUrl}/memory/universal-search?q=${encodeURIComponent(args.query)}&limit=${limit}`,
              { timeoutMs: 10_000 },
            )
            const hits = result?.hits ?? []
            if (hits.length === 0) return { content: [{ type: 'text', text: `No engrams with tag "${args.query}".` }] }
            let out = `## Tag: "${args.query}" (${hits.length})\n\n`
            for (const hit of hits) {
              out += `- **[${hit.nodeType ?? '?'}] ${hit.id}**`
              if (hit.potentiation != null) out += ` (pot: ${typeof hit.potentiation === 'number' ? hit.potentiation.toFixed(2) : hit.potentiation})`
              if (hit.tags?.length) out += ` [${hit.tags.join(', ')}]`
              out += `: ${(hit.content ?? '').slice(0, 400).replace(/\n/g, ' ')}\n`
            }
            return { content: [{ type: 'text', text: out }] }
          }

          case 'by_type': {
            if (!args.nodeType) return { content: [{ type: 'text', text: 'nodeType required for by_type action.' }], isError: true }
            const result = await fetchJson(
              `${adminUrl}/memory/by-type/${encodeURIComponent(args.nodeType)}?limit=${limit}`,
              { timeoutMs: 10_000 },
            )
            const engrams = result?.engrams ?? []
            if (engrams.length === 0) return { content: [{ type: 'text', text: `No engrams of type "${args.nodeType}".` }] }
            let out = `## Type: "${args.nodeType}" (${engrams.length})\n\n`
            for (const e of engrams) {
              out += `- **${e.id}**`
              if (e.potentiation != null) out += ` (pot: ${typeof e.potentiation === 'number' ? e.potentiation.toFixed(2) : e.potentiation})`
              if (e.tags?.length) out += ` [${e.tags.join(', ')}]`
              if (e.createdAt) out += ` (created: ${String(e.createdAt).slice(0, 10)})`
              out += `: ${(e.content ?? '').slice(0, 400).replace(/\n/g, ' ')}\n`
            }
            return { content: [{ type: 'text', text: out }] }
          }

          case 'popular': {
            const result = await fetchJson(
              `${adminUrl}/memory/popular?limit=${limit}`,
              { timeoutMs: 10_000 },
            )
            const engrams = result?.engrams ?? []
            if (engrams.length === 0) return { content: [{ type: 'text', text: 'No engrams found.' }] }
            let out = `## Popular (top ${engrams.length} by potentiation)\n\n`
            for (const e of engrams) {
              out += `- **[${e.nodeType ?? '?'}] ${e.id}**`
              if (e.potentiation != null) out += ` (pot: ${typeof e.potentiation === 'number' ? e.potentiation.toFixed(3) : e.potentiation})`
              if (e.tags?.length) out += ` [${e.tags.join(', ')}]`
              out += `: ${(e.content ?? '').slice(0, 400).replace(/\n/g, ' ')}\n`
            }
            return { content: [{ type: 'text', text: out }] }
          }

          case 'neighborhood': {
            if (!args.query) return { content: [{ type: 'text', text: 'query (engram ID) required for neighborhood action.' }], isError: true }
            const maxDepth = Math.min(args.maxDepth ?? 2, 5)
            const body: any = { startId: args.query, maxDepth }
            if (args.edgeType) body.edgeTypes = [args.edgeType]
            const result = await fetchJson(`${adminUrl}/memory/graph-search`, {
              method: 'POST',
              body,
              timeoutMs: 10_000,
            })
            const nodes = result?.nodes ?? []
            const edges = result?.edges ?? []
            if (nodes.length === 0) return { content: [{ type: 'text', text: `No neighborhood found for "${args.query}".` }] }
            let out = `## Neighborhood: ${args.query} (depth ${result?.maxDepth ?? maxDepth}, ${nodes.length} nodes, ${edges.length} edges)\n\n`
            // Group nodes by depth
            const byDepth = new Map<number, typeof nodes>()
            for (const n of nodes) {
              const d = n.depth ?? 0
              if (!byDepth.has(d)) byDepth.set(d, [])
              byDepth.get(d)!.push(n)
            }
            for (const [depth, ns] of [...byDepth.entries()].sort((a, b) => a[0] - b[0])) {
              out += `### Depth ${depth}\n`
              for (const n of ns) {
                out += `- **[${n.nodeType ?? '?'}] ${n.id}**: ${(n.content ?? '').slice(0, 200).replace(/\n/g, ' ')}\n`
              }
              out += '\n'
            }
            if (edges.length > 0) {
              out += `### Edges\n`
              for (const e of edges) {
                out += `- ${e.sourceId} → **${e.edgeType}** → ${e.targetId}\n`
              }
            }
            return { content: [{ type: 'text', text: out }] }
          }

          case 'tensions': {
            const params = new URLSearchParams()
            if (args.minPotentiation != null) params.set('minPotentiation', String(args.minPotentiation))
            if (args.limit != null) params.set('limit', String(args.limit))
            const qs = params.toString()
            const result = await fetchJson(`${adminUrl}/memory/tensions${qs ? '?' + qs : ''}`, { timeoutMs: 10_000 })
            const report = result?.report
            if (!report || !report.pairs?.length) return { content: [{ type: 'text', text: 'No tensions detected.' }] }
            let out = `## Tensions (${report.pairs.length} pairs, total tension: ${typeof report.totalTension === 'number' ? report.totalTension.toFixed(3) : '?'})\n\n`
            out += `${report.recommendation ?? ''}\n\n`
            for (const p of report.pairs) {
              out += `- **Tension ${typeof p.tension === 'number' ? p.tension.toFixed(3) : p.tension}**:\n`
              out += `  - A: [${p.engramA?.nodeType ?? '?'}] ${p.engramA?.id ?? '?'}: ${(p.engramA?.content ?? '').slice(0, 200)}\n`
              out += `  - B: [${p.engramB?.nodeType ?? '?'}] ${p.engramB?.id ?? '?'}: ${(p.engramB?.content ?? '').slice(0, 200)}\n`
            }
            return { content: [{ type: 'text', text: out }] }
          }

          default:
            return { content: [{ type: 'text', text: `Unknown browse action: ${action}` }], isError: true }
        }
      }

      case 'self_model': {
        let result = await fetchJson(
          `${adminUrl}/self-model?query=${encodeURIComponent(args.query)}&limit=${args.limit ?? 5}`,
          { timeoutMs: 10_000 },
        ).catch(() => null)
        if (!result || !result.results && !result.hits) {
          result = await fetchJson(`${adminUrl}/self-model/retrieve`, {
            method: 'POST',
            body: { query: args.query, limit: args.limit ?? 5 },
            timeoutMs: 10_000,
          }).catch(() => null)
        }
        const results = result?.results ?? result?.hits ?? []
        if (results.length === 0) {
          return { content: [{ type: 'text', text: `No self-model entries for "${args.query}".` }] }
        }
        let out = `## Self-Model: "${args.query}"\n\n`
        for (const r of results) {
          out += `- **${r.nodeType ?? r.type ?? 'concept'}**: ${(r.content ?? r.description ?? '').slice(0, 500)}\n`
        }
        return { content: [{ type: 'text', text: out }] }
      }

      default:
        return { content: [{ type: 'text', text: `Unknown cognitive tool: ${name}` }], isError: true }
    }
  } catch (err: any) {
    return { content: [{ type: 'text', text: `Cognitive enrichment error: ${err.message ?? String(err)}` }], isError: true }
  }
}
