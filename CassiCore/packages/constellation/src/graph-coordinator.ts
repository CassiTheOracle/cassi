/**
 * CrossBranchGraphCoordinator — Live graph-based discovery sharing across constellation branches.
 *
 * When a branch writes a brainstem discovery engram to the MnemicField, this
 * coordinator runs typed-edge propagation to find sibling branches and pushes
 * relevant discoveries into their context. This enables real-time cross-branch
 * awareness: Branch B sees that Branch A just discovered a race condition in
 * the same module, even before A's Helix completes.
 *
 * Integration points:
 *   1. onBranchDiscovery() — called after brainstem writes a discovery engram
 *   2. querySiblingDiscoveries() — on-demand graph walk for a branch to find
 *      what its siblings have discovered (driven by Corpus or a tool call)
 */

import type { MnemicField } from '../mnemic-field/index.js'
import type { Engram } from '../mnemic-field/types.js'
import { GraphAttnPropagator } from '../mnemic-field/graph-attn-propagator.js'
import type { ILogger } from '../../../types/interfaces.js'

export interface SiblingDiscovery {
  engram: Engram
  sourceBranch: string
  charge: number
  sharedEdges: string[]
}

export interface CrossBranchGraphCoordinatorConfig {
  maxHops: number
  decay: number
  discoveryTTLMs: number
}

const DEFAULT_CONFIG: CrossBranchGraphCoordinatorConfig = {
  maxHops: 3,
  decay: 0.7,
  discoveryTTLMs: 600_000,
}

export class CrossBranchGraphCoordinator {
  private field: MnemicField
  private logger: ILogger
  private config: CrossBranchGraphCoordinatorConfig
  private propagator: GraphAttnPropagator

  /** helixId → [engramId, ...] — recent discovery engrams written by each branch */
  private branchDiscoveries = new Map<string, string[]>()
  private discoveryTimestamps = new Map<string, number>()

  constructor(field: MnemicField, logger: ILogger, config?: Partial<CrossBranchGraphCoordinatorConfig>) {
    this.field = field
    this.logger = logger.child('graph-coordinator')
    this.config = { ...DEFAULT_CONFIG, ...config }
    this.propagator = new GraphAttnPropagator(field as any)
  }

  /**
   * Record a discovery engram written by a branch and propagate to siblings.
   * Called immediately after the brainstem writes a `helix-discovery` engram.
   */
  onBranchDiscovery(helixId: string, engramId: string): SiblingDiscovery[] {
    const discoveries = this.branchDiscoveries.get(helixId) ?? []
    discoveries.push(engramId)
    this.branchDiscoveries.set(helixId, discoveries)
    this.discoveryTimestamps.set(engramId, Date.now())

    this.evictStale()

    return this.propagateToSiblings(helixId, engramId)
  }

  /**
   * Query what sibling branches have discovered that's relevant to the given
   * branch's goal. Runs GraphAttnPropagator from the branch's engram to find
   * sibling discoveries via shared edges.
   */
  querySiblingDiscoveries(helixId: string, seedEngramId?: string): SiblingDiscovery[] {
    this.evictStale()

    const seedId = seedEngramId ?? this.findBranchEngramId(helixId)
    if (!seedId) {
      // No engram yet — try propagating from sibling discovery engrams directly
      return this.broadPhaseDiscoveryScan(helixId)
    }

    return this.propagateFromSeed(helixId, seedId)
  }

  /**
   * Perform a broad scan: propagate from sibling branches' discovery engrams
   * to find anything that might be relevant to the querying branch.
   */
  private broadPhaseDiscoveryScan(excludeHelixId: string): SiblingDiscovery[] {
    const seedIds: string[] = []
    for (const [hid, discoveryIds] of this.branchDiscoveries) {
      if (hid === excludeHelixId) continue
      seedIds.push(...discoveryIds.slice(-3))
    }
    if (seedIds.length === 0) return []

    try {
      const results = this.propagator.propagate({
        seedIds,
        edgeTypes: ['spawned_from', 'part_of', 'similar_to'],
        maxHops: 2,
        topN: 5,
        minCharge: 0.03,
        hopDecay: this.config.decay,
      })
      return this.shapeResults(results, excludeHelixId)
    } catch (err) {
      this.logger.warn('Broad phase discovery scan failed', { error: String(err) })
      return []
    }
  }

  /**
   * Propagate from the branch's seed engram to find sibling discoveries.
   */
  private propagateFromSeed(helixId: string, seedId: string): SiblingDiscovery[] {
    try {
      const results = this.propagator.propagate({
        seedIds: [seedId],
        edgeTypes: ['spawned_from', 'part_of', 'similar_to', 'temporal_neighbor'],
        maxHops: this.config.maxHops,
        topN: 8,
        minCharge: 0.02,
        hopDecay: this.config.decay,
      })
      return this.shapeResults(results, helixId)
    } catch (err) {
      this.logger.warn('Propagation from seed failed', { helixId, error: String(err) })
      return []
    }
  }

  /**
   * Propagate a freshly written discovery to sibling branches.
   */
  private propagateToSiblings(helixId: string, discoveryId: string): SiblingDiscovery[] {
    const siblingIds = this.getSiblingBranchIds(helixId)
    if (siblingIds.length === 0) return []

    try {
      const results = this.propagator.propagate({
        seedIds: [discoveryId],
        edgeTypes: ['spawned_from', 'part_of', 'similar_to'],
        maxHops: 2,
        topN: 6,
        minCharge: 0.03,
        hopDecay: this.config.decay,
      })
      return this.shapeResults(results, helixId)
        .filter(d => siblingIds.includes(d.sourceBranch))
    } catch (err) {
      this.logger.warn('Propagation to siblings failed', { helixId, error: String(err) })
      return []
    }
  }

  /**
   * Format discoveries as context text for injection into an LLM prompt.
   */
  formatDiscoveriesForContext(discoveries: SiblingDiscovery[], maxPerBranch: number = 3): string {
    if (discoveries.length === 0) return ''

    const lines: string[] = [
      '┏━ Live Cross-Branch Graph Discoveries ━┓',
      '',
    ]

    const grouped = new Map<string, SiblingDiscovery[]>()
    for (const d of discoveries) {
      const list = grouped.get(d.sourceBranch) ?? []
      if (list.length < maxPerBranch) {
        list.push(d)
        grouped.set(d.sourceBranch, list)
      }
    }

    for (const [branchId, deps] of grouped) {
      lines.push(`  Branch ${branchId.slice(-8)}${grouped.size > 1 ? ':' : ''}`)
      for (const d of deps) {
        const preview = (d.engram.content ?? '').slice(0, 140)
        const edges = d.sharedEdges.length > 0 ? ` [via ${d.sharedEdges.join(', ')}]` : ''
        lines.push(`    • [${(d.charge * 100).toFixed(0)}%]${edges} ${preview}`)
      }
      lines.push('')
    }

    lines.push('┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛')
    return lines.join('\n')
  }

  private getSiblingBranchIds(excludeHelixId: string): string[] {
    const ids: string[] = []
    for (const hid of this.branchDiscoveries.keys()) {
      if (hid !== excludeHelixId) ids.push(hid)
    }
    return ids
  }

  private findBranchEngramId(helixId: string): string | undefined {
    const discoveries = this.branchDiscoveries.get(helixId)
    return discoveries?.[discoveries.length - 1]
  }

  private shapeResults(
    propagated: Array<{ engram: Engram; charge: number; paths: Array<{ hops: Array<{ edgeType: string }> }> }>,
    excludeHelixId: string,
  ): SiblingDiscovery[] {
    const results: SiblingDiscovery[] = []
    for (const pe of propagated) {
      const sourceBranch = this.findOwningBranch(pe.engram.id)
      if (!sourceBranch || sourceBranch === excludeHelixId) continue

      const sharedEdges = new Set<string>()
      for (const path of pe.paths) {
        for (const hop of path.hops) {
          sharedEdges.add(hop.edgeType)
        }
      }

      results.push({
        engram: pe.engram,
        sourceBranch,
        charge: pe.charge,
        sharedEdges: Array.from(sharedEdges),
      })
    }
    results.sort((a, b) => b.charge - a.charge)
    return results
  }

  private findOwningBranch(engramId: string): string | undefined {
    for (const [hid, ids] of this.branchDiscoveries) {
      if (ids.includes(engramId)) return hid
    }
    return undefined
  }

  private evictStale(): void {
    const cutoff = Date.now() - this.config.discoveryTTLMs
    for (const [engramId, ts] of this.discoveryTimestamps) {
      if (ts < cutoff) {
        for (const [hid, ids] of this.branchDiscoveries) {
          const idx = ids.indexOf(engramId)
          if (idx >= 0) {
            ids.splice(idx, 1)
            if (ids.length === 0) this.branchDiscoveries.delete(hid)
          }
        }
        this.discoveryTimestamps.delete(engramId)
      }
    }
  }
}
