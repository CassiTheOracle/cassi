/**
 * GraphAttnPropagator — Typed-edge-aware signal propagation over the mnemic graph.
 *
 * Traverses specified edge types (e.g. `spawned_from`, `part_of`) from seed engrams,
 * weighting propagation by per-edge-type multipliers and decaying signal with hop distance.
 * Returns the top-N charged engrams along with their propagation paths from seeds.
 *
 * This is a graph-attention–style mechanism: different edge types receive different
 * attention multipliers, and accumulated charge captures multi-hop structural relevance.
 *
 * Uses the Cortex API exclusively for graph traversal and engram retrieval.
 */

import type { Cortex } from './cortex.js'
import type { Engram, MnemicSynapse, SynapseType } from './types.js'
import { SYNAPSE_PROPAGATION } from './types.js'


// Public types


/** A single hop in a propagation path. */
export interface PropagationHop {
  engramId: string
  edgeType: SynapseType
  direction: 'outgoing' | 'incoming'
  /** Effective weight applied: baseProp × multiplier × syn.weight */
  weight: number
  charge: number
  hop: number
}

/** A traced path from a seed to a reached engram. */
export interface PropagationPath {
  seedId: string
  targetId: string
  hops: PropagationHop[]
}

/** A scored engram produced by propagation. */
export interface PropagatedEngram {
  engram: Engram
  charge: number
  paths: PropagationPath[]
}

/** Configuration for a propagation run. */
export interface GraphAttnPropagatorOpts {
  seedIds: string[]
  edgeTypes?: SynapseType[]
  edgeMultipliers?: Partial<Record<SynapseType, number>>
  defaultMultiplier?: number
  hopDecay?: number
  maxHops?: number
  topN?: number
  minCharge?: number
  followOutgoing?: boolean
  followIncoming?: boolean
  seedCharge?: number
  recordSpikes?: boolean
  taskContext?: string
}


// Defaults


const DEFAULT_EDGE_TYPES: SynapseType[] = ['spawned_from', 'part_of']

const DEFAULT_OPTS = {
  edgeTypes: DEFAULT_EDGE_TYPES,
  defaultMultiplier: 0.5,
  hopDecay: 0.7,
  maxHops: 3,
  topN: 20,
  minCharge: 0.01,
  followOutgoing: true,
  followIncoming: true,
  seedCharge: 1.0,
  recordSpikes: false,
  taskContext: 'graph-attn-propagation',
} as const


// Internal BFS state


interface FrontierEntry {
  engramId: string
  hop: number
  incomingCharge: number
  pathSoFar: PropagationHop[]
  seedId: string
}


// GraphAttnPropagator


export class GraphAttnPropagator {
  private readonly cortex: Cortex

  constructor(cortex: Cortex) {
    this.cortex = cortex
  }

  /**
   * Run typed-edge-aware signal propagation from the given seeds.
   *
   * Algorithm:
   *  1. Seed each start engram with `seedCharge`.
   *  2. BFS frontier expands through edges whose type is in `edgeTypes`.
   *  3. Each edge contributes charge = incoming × multiplier(edgeType) × synapseWeight × hopDecay^hop.
   *  4. Charge accumulates at each engram (additive — multiple paths reinforce).
   *  5. After BFS completes, sort by total charge and return top-N with their best paths.
   */
  propagate(opts: GraphAttnPropagatorOpts): PropagatedEngram[] {
    const {
      seedIds,
      edgeTypes,
      edgeMultipliers,
      defaultMultiplier,
      hopDecay,
      maxHops,
      topN,
      minCharge,
      followOutgoing,
      followIncoming,
      seedCharge,
      recordSpikes,
      taskContext,
    } = {
      ...DEFAULT_OPTS,
      ...opts,
    }

    if (seedIds.length === 0) return []

    const allowedTypes = new Set<SynapseType>(edgeTypes)
    const charges = new Map<string, number>()
    const pathBySeed = new Map<string, PropagationPath>()

    const frontier: FrontierEntry[] = []
    for (const seedId of seedIds) {
      const engram = this.cortex.getEngram(seedId)
      if (!engram) continue
      charges.set(seedId, (charges.get(seedId) ?? 0) + seedCharge)
      frontier.push({
        engramId: seedId,
        hop: 0,
        incomingCharge: seedCharge,
        pathSoFar: [],
        seedId,
      })
    }

    const visited = new Set<string>()
    let head = 0

    while (head < frontier.length) {
      const entry = frontier[head]!
      head++

      if (entry.hop >= maxHops) continue

      const visitKey = `${entry.engramId}:${entry.hop}`
      if (visited.has(visitKey)) continue
      visited.add(visitKey)

      const synapses = this.gatherSynapses(entry.engramId, followOutgoing, followIncoming)

      for (const syn of synapses) {
        if (!allowedTypes.has(syn.edgeType as SynapseType)) continue

        const isOutgoing = syn.sourceId === entry.engramId
        const neighborId = isOutgoing ? syn.targetId : syn.sourceId

        const baseProp = SYNAPSE_PROPAGATION[syn.edgeType as SynapseType] ?? defaultMultiplier
        const multiplier = edgeMultipliers?.[syn.edgeType as SynapseType] ?? 1.0
        const effectiveWeight = baseProp * multiplier * syn.weight
        const decay = Math.pow(hopDecay, entry.hop + 1)
        const contributedCharge = entry.incomingCharge * effectiveWeight * decay

        if (contributedCharge < minCharge) continue

        charges.set(neighborId, (charges.get(neighborId) ?? 0) + contributedCharge)

        const hop: PropagationHop = {
          engramId: neighborId,
          edgeType: syn.edgeType as SynapseType,
          direction: isOutgoing ? 'outgoing' : 'incoming',
          weight: effectiveWeight,
          charge: contributedCharge,
          hop: entry.hop + 1,
        }

        const pathKey = `${entry.seedId}\0${neighborId}`
        const existing = pathBySeed.get(pathKey)
        if (!existing || contributedCharge > existing.hops[existing.hops.length - 1]!.charge) {
          pathBySeed.set(pathKey, {
            seedId: entry.seedId,
            targetId: neighborId,
            hops: [...entry.pathSoFar, hop],
          })
        }

        frontier.push({
          engramId: neighborId,
          hop: entry.hop + 1,
          incomingCharge: contributedCharge,
          pathSoFar: [...entry.pathSoFar, hop],
          seedId: entry.seedId,
        })
      }
    }

    if (recordSpikes) {
      for (const [id, charge] of charges) {
        if (seedIds.includes(id)) continue
        try {
          this.cortex.recordSpike({
            engramId: id,
            magnitude: Math.min(charge, 1.0),
            taskContext,
            outcome: 'unknown',
          })
        } catch { }
      }
    }

    const results: PropagatedEngram[] = []
    for (const [engramId, charge] of charges) {
      if (charge < minCharge) continue
      const engram = this.cortex.getEngram(engramId)
      if (!engram) continue

      const paths: PropagationPath[] = []
      for (const path of pathBySeed.values()) {
        if (path.targetId === engramId) paths.push(path)
      }
      results.push({ engram, charge, paths })
    }

    results.sort((a, b) => b.charge - a.charge)
    return results.slice(0, topN)
  }

  /**
   * Format propagation results as a structured text block for LLM prompts.
   */
  renderForPrompt(results: PropagatedEngram[], seed?: Engram): string {
    if (results.length === 0) return ''
    const lines: string[] = [
      '━━━ Graph Attention Context ━━━',
    ]
    if (seed) {
      lines.push(`seed: ${seed.nodeType} "${truncate(seed.content, 100)}"`)
    }
    lines.push(`charges: ${results.length} engrams propagated`)
    lines.push('')

    for (let i = 0; i < results.length; i++) {
      const r = results[i]
      const e = r.engram
      lines.push(
        `[${i + 1}] ${e.nodeType}  charge=${r.charge.toFixed(3)}`,
        `    "${truncate(e.content, 140)}"`,
      )
      if (r.paths.length > 0) {
        for (const p of r.paths.slice(0, 2)) {
          const pathStr = p.hops.map(h =>
            `${h.hop > 0 ? ' → ' : ''}${h.edgeType}(w=${h.weight.toFixed(2)})`
          ).join('')
          lines.push(`    path: ${pathStr}`)
        }
        const total = r.paths.length
        if (total > 2) lines.push(`    ... and ${total - 2} more paths`)
      }
      lines.push('')
    }

    lines.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    return lines.join('\n')
  }

  /**
   * Convenience: propagate with system-wide SYNAPSE_PROPAGATION weights.
   */
  propagateWithSystemWeights(
    seedIds: string[],
    edgeTypes?: SynapseType[],
    overrides?: Partial<Omit<GraphAttnPropagatorOpts, 'seedIds' | 'edgeTypes'>>,
  ): PropagatedEngram[] {
    return this.propagate({ seedIds, edgeTypes, ...overrides })
  }

  // ---- private -----------------------------------------------------------

  private gatherSynapses(
    engramId: string,
    followOutgoing: boolean,
    followIncoming: boolean,
  ): MnemicSynapse[] {
    const synapses: MnemicSynapse[] = []

    if (followOutgoing) {
      synapses.push(...this.cortex.getNeighborSynapses(engramId, 'outgoing'))
    }
    if (followIncoming) {
      if (followOutgoing) {
        const outgoing = new Set(
          synapses.map(s => `${s.sourceId}\0${s.targetId}\0${s.edgeType}`),
        )
        for (const s of this.cortex.getNeighborSynapses(engramId, 'incoming')) {
          if (!outgoing.has(`${s.sourceId}\0${s.targetId}\0${s.edgeType}`)) {
            synapses.push(s)
          }
        }
      } else {
        synapses.push(...this.cortex.getNeighborSynapses(engramId, 'incoming'))
      }
    }
    return synapses
  }
}


// Utility


function truncate(s: string, maxLen: number): string {
  if (s.length <= maxLen) return s
  return s.slice(0, maxLen - 1) + '…'
}
