import type { ILogger } from '../../../../types/interfaces.js'
import type { MnemicField } from '../../mnemic-field/index.js'
import type { SynapseType } from '../../mnemic-field/types.js'
import type { ConstellationNode, ConstellationResult } from '../types.js'

export interface OutcomeConsolidatorConfig {
  learningRate?: number
  minWeight?: number
  maxWeight?: number
  neutralScore?: number
  edgeTypes?: SynapseType[]
}

const DEFAULT_CONFIG = {
  learningRate: 0.05,
  minWeight: 0.01,
  maxWeight: 1.0,
  neutralScore: 0.5,
  edgeTypes: ['spawned_from', 'part_of', 'similar_to', 'temporal_neighbor'] as SynapseType[],
}

export interface OutcomeConsolidationResult {
  edgesConsidered: number
  edgesUpdated: number
  branchesProcessed: number
  branchesSkipped: number
}

export class OutcomeConsolidator {
  private logger: ILogger
  private field: MnemicField
  private config: typeof DEFAULT_CONFIG

  constructor(
    field: MnemicField,
    logger: ILogger,
    config?: OutcomeConsolidatorConfig,
  ) {
    this.field = field
    this.logger = logger.child('outcome-consolidator')
    this.config = { ...DEFAULT_CONFIG, ...config }
  }

  consolidate(
    result: ConstellationResult,
    nodes: Map<string, ConstellationNode>,
    branchEngramIds: Map<string, string>,
    clusterNodeScores?: Map<string, number>,
  ): OutcomeConsolidationResult {
    const r: OutcomeConsolidationResult = {
      edgesConsidered: 0,
      edgesUpdated: 0,
      branchesProcessed: 0,
      branchesSkipped: 0,
    }

    const updates: Array<{ sourceId: string; targetId: string; edgeType: string; weight: number }> = []

    for (const [helixId, node] of nodes) {
      const branchId = branchEngramIds.get(helixId)
      if (!branchId) {
        r.branchesSkipped++
        continue
      }

      const score = clusterNodeScores ? 
        (clusterNodeScores.get(helixId) ?? this.config.neutralScore) :
        this.computeBranchScore(node)

      r.branchesProcessed++

      for (const edgeType of this.config.edgeTypes) {
        try {
          const outgoing = this.field.getTypedSynapses(branchId, edgeType, 'out')
          for (const syn of outgoing) {
            const delta = (score - this.config.neutralScore) * this.config.learningRate
            const newWeight = clamp(syn.weight + delta, this.config.minWeight, this.config.maxWeight)
            r.edgesConsidered++
            if (Math.abs(newWeight - syn.weight) < 0.001) continue
            updates.push({
              sourceId: syn.sourceId,
              targetId: syn.targetId,
              edgeType: syn.edgeType,
              weight: newWeight,
            })
          }

          const incoming = this.field.getTypedSynapses(branchId, edgeType, 'in')
          for (const syn of incoming) {
            const delta = (score - this.config.neutralScore) * this.config.learningRate
            const newWeight = clamp(syn.weight + delta, this.config.minWeight, this.config.maxWeight)
            r.edgesConsidered++
            if (Math.abs(newWeight - syn.weight) < 0.001) continue
            updates.push({
              sourceId: syn.sourceId,
              targetId: syn.targetId,
              edgeType: syn.edgeType,
              weight: newWeight,
            })
          }
        } catch (err) {
          this.logger.debug('Failed to gather synapses for edge type', {
            branchId,
            edgeType,
            error: String(err),
          })
        }
      }
    }

    if (updates.length > 0) {
      try {
        r.edgesUpdated = this.field.bulkUpdateSynapseWeights(updates)
        this.logger.info('Outcome consolidation complete', {
          branchesProcessed: r.branchesProcessed,
          edgesConsidered: r.edgesConsidered,
          edgesUpdated: r.edgesUpdated,
        })
      } catch (err) {
        this.logger.warn('Failed to apply synapse weight updates', { error: String(err) })
        r.edgesUpdated = 0
      }
    }

    return r
  }

  private computeBranchScore(node: ConstellationNode): number {
    const bonus = node.status === 'completed' ? 1.0
      : node.status === 'degraded' ? 0.5
      : 0.0

    const unityResult = node.postureResults.get('unity')
    const confidence = unityResult?.confidence ?? this.config.neutralScore

    return clamp(confidence * bonus, 0, 1)
  }
}

function clamp(v: number, min: number, max: number): number {
  return v < min ? min : v > max ? max : v
}
