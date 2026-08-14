import type { GlobalWorkspace } from '../vendor/workspace/global-workspace.js'
import type { SynapseType } from '@cassicore/mnemic-field'
import { GraphAttnPropagator, type PropagatedEngram } from '@cassicore/mnemic-field'
import type { ILogger } from '../vendor/types/interfaces.js'

export const DEFAULT_ATTENTION_BRIDGE_CONFIG = {
  cacheTTLMs: 15_000,
  maxHops: 2,
  topN: 5,
  minCharge: 0.02,
  hopDecay: 0.6,
  edgeTypes: ['spawned_from', 'part_of', 'similar_to', 'temporal_neighbor'],
}

export interface AttentionBridgeConfig {
  cacheTTLMs?: number
  maxHops?: number
  topN?: number
  minCharge?: number
  hopDecay?: number
  edgeTypes?: SynapseType[]
}

export interface AttentionContext {
  content: string
  charge: number
  sourceCount: number
  engramTypes: string[]
}

export class GraphAttentionBridge {
  private propagator: GraphAttnPropagator
  private branchEngramIds: Map<string, string>
  private logger: ILogger
  private config: Required<AttentionBridgeConfig>
  private lastInjectionTimestamps = new Map<string, number>()
  private invalidatedBranches = new Set<string>()

  constructor(
    propagator: GraphAttnPropagator,
    branchEngramIds: Map<string, string>,
    logger: ILogger,
    config?: AttentionBridgeConfig,
  ) {
    this.propagator = propagator
    this.branchEngramIds = branchEngramIds
    this.logger = logger.child('graph-attention-bridge')
    this.config = {
      cacheTTLMs: config?.cacheTTLMs ?? DEFAULT_ATTENTION_BRIDGE_CONFIG.cacheTTLMs,
      maxHops: config?.maxHops ?? DEFAULT_ATTENTION_BRIDGE_CONFIG.maxHops,
      topN: config?.topN ?? DEFAULT_ATTENTION_BRIDGE_CONFIG.topN,
      minCharge: config?.minCharge ?? DEFAULT_ATTENTION_BRIDGE_CONFIG.minCharge,
      hopDecay: config?.hopDecay ?? DEFAULT_ATTENTION_BRIDGE_CONFIG.hopDecay,
      edgeTypes: config?.edgeTypes ?? DEFAULT_ATTENTION_BRIDGE_CONFIG.edgeTypes as SynapseType[],
    }
  }

  injectToWorkspace(
    helixId: string,
    workspace: GlobalWorkspace,
  ): string | null {
    const ctx = this.compute(helixId)
    if (!ctx) return null

    const signalId = `graph-attn-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`

    try {
      workspace.submit({
        signalId,
        source: `bridge:${helixId}`,
        sessionId: helixId,
        type: 'memory',
        content: ctx.content,
        createdAt: Date.now(),
        luminance: {
          novelty: 0.5,
          urgency: 0.4,
          relevance: 0.7,
          sourceCredibility: 0.6,
          cognitiveResonance: 0.5,
          strategicImportance: 0.3,
          composite: 0.55,
        },
        urgencyHint: 0.4,
        metadata: {
          bridge: true,
          posture: 'graph-attention',
          kind: 'graph-context',
          sourceCount: ctx.sourceCount,
          engramTypes: ctx.engramTypes,
          topCharge: ctx.charge,
        },
      })
    } catch (err) {
      this.logger.warn('Failed to submit graph attention context to workspace', {
        helixId,
        error: String(err),
      })
      this.lastInjectionTimestamps.set(helixId, Date.now())
      return null
    }

    this.lastInjectionTimestamps.set(helixId, Date.now())
    this.invalidatedBranches.delete(helixId)

    this.logger.debug('Injected graph attention context', {
      helixId,
      sourceCount: ctx.sourceCount,
      engramTypes: ctx.engramTypes.length,
      topCharge: ctx.charge.toFixed(3),
    })

    return signalId
  }

  invalidateBranch(helixId: string): void {
    this.invalidatedBranches.add(helixId)
  }

  private compute(helixId: string): AttentionContext | null {
    const lastTs = this.lastInjectionTimestamps.get(helixId)
    if (lastTs && !this.invalidatedBranches.has(helixId)) {
      const elapsed = Date.now() - lastTs
      if (elapsed < this.config.cacheTTLMs) return null
    }

    const branchId = this.branchEngramIds.get(helixId)
    if (!branchId) return null

    let propagated: PropagatedEngram[]
    try {
      propagated = this.propagator.propagate({
        seedIds: [branchId],
        edgeTypes: this.config.edgeTypes,
        maxHops: this.config.maxHops,
        topN: this.config.topN,
        minCharge: this.config.minCharge,
        hopDecay: this.config.hopDecay,
      })
    } catch (err) {
      this.logger.warn('Attention graph walk failed', { helixId, error: String(err) })
      return null
    }

    const filtered = propagated.filter(p => p.engram.id !== branchId)
    if (filtered.length === 0) return null

    const formatted = this.format(filtered)

    const engramTypes = Array.from(new Set(filtered.map(p => p.engram.nodeType ?? 'fact')))

    return {
      content: formatted,
      charge: filtered[0]!.charge,
      sourceCount: filtered.length,
      engramTypes,
    }
  }

  private format(results: PropagatedEngram[]): string {
    const lines: string[] = [
      '[MnemicGraph Attention — related engrams surfaced from knowledge graph]',
      '',
    ]

    for (const r of results) {
      const e = r.engram
      const chargeStr = (r.charge * 100).toFixed(0)
      const preview = truncate(e.content, 160)
      const edgeStr = r.paths.length > 0
        ? ` via ${r.paths[0]!.hops.map(h => h.edgeType).join(' → ')}`
        : ''
      const typeTag = e.nodeType ?? 'fact'
      const tagStr = e.tags?.length ? ` [${e.tags.slice(0, 3).join(', ')}]` : ''
      lines.push(`  [${chargeStr}%] ${typeTag}${edgeStr}${tagStr}`)
      lines.push(`    ${preview}`)
      lines.push('')
    }

    return lines.join('\n')
  }
}

function truncate(s: string, maxLen: number): string {
  if (s.length <= maxLen) return s
  return s.slice(0, maxLen - 1) + '…'
}
