import type { ILogger } from '../../../../types/interfaces.js'
import type { MnemicField } from '../index.js'
import type { KindlingOptions, MnemicRetrievalHit, Engram } from '../types.js'
import type { SelfModelField } from './self-model-field.js'
import {
  BRIDGE_DEFAULTS, SELF_MODEL_KINDLING_DEFAULTS,
  type BridgeConfig, type CrossFieldRetrievalHit, type CrossFieldResult,
  type PortalMetadata,
} from './types.js'

/**
 * InterFieldBridge — connects the episodic Mnemic Field to the Self-Model Field.
 *
 * Cross-field activation works via cross-pollination:
 * 1. Kindle in both fields independently
 * 2. Top hits from field A boost scores of portal-connected engrams in field B
 * 3. Merge and rank results from both fields
 *
 * Portal engrams serve as persistent connection points that accumulate
 * synapses to related engrams in their local field, creating natural
 * activation pathways for cross-field boosting.
 */
export class InterFieldBridge {
  private episodicField: MnemicField
  private selfModelField: SelfModelField
  private logger: ILogger
  private config: BridgeConfig
  private portalPairs: Map<string, { episodicId: string; selfModelId: string }> = new Map()
  /** Reverse index: portal engram ID → concept name. O(1) lookup. */
  private portalIdToConcept: Map<string, string> = new Map()

  constructor(
    episodicField: MnemicField,
    selfModelField: SelfModelField,
    logger: ILogger,
    config?: Partial<BridgeConfig>,
  ) {
    this.episodicField = episodicField
    this.selfModelField = selfModelField
    this.logger = logger.child ? logger.child('inter-field-bridge') : logger
    this.config = { ...BRIDGE_DEFAULTS, ...config }
    this.logger.info('InterFieldBridge initialized', {
      dampening: this.config.crossFieldDampening,
      maxPortals: this.config.maxPortals,
    })
  }

  /**
   * Create a portal pair — one portal engram in each field, linked together.
   * Returns null if the portal limit has been reached.
   */
  createPortalPair(concept: string): {
    episodicPortal: Engram
    selfModelPortal: Engram
  } | null {
    if (this.portalPairs.has(concept)) {
      const existing = this.portalPairs.get(concept)!
      const ep = this.episodicField.get(existing.episodicId)
      const sm = this.selfModelField.get(existing.selfModelId)
      if (ep && sm) return { episodicPortal: ep, selfModelPortal: sm }
    }

    if (this.portalPairs.size >= this.config.maxPortals) {
      this.logger.warn('Portal limit reached, refusing creation', {
        current: this.portalPairs.size,
        max: this.config.maxPortals,
        concept,
      })
      return null
    }

    const selfModelPortal = this.selfModelField.createPortal(concept, 'pending', 'self-model')
    const episodicPortal = this.episodicField.store({
      content: `[portal:${concept}] Bridge to self-model field`,
      nodeType: 'portal',
      tags: ['portal', concept],
      provenance: 'inter-field-bridge',
      metadata: {
        fieldId: 'episodic',
        linkedPortalId: selfModelPortal.id,
        bridgeConcept: concept,
        dampening: this.config.crossFieldDampening,
      } satisfies PortalMetadata as unknown as Record<string, unknown>,
    })

    this.selfModelField.getField().update(selfModelPortal.id, {
      metadata: {
        ...selfModelPortal.metadata,
        linkedPortalId: episodicPortal.id,
      },
    })

    this.registerPortalPair(concept, episodicPortal.id, selfModelPortal.id)
    this.logger.debug('Portal pair created', { concept, episodicId: episodicPortal.id, selfModelId: selfModelPortal.id })

    return { episodicPortal, selfModelPortal }
  }

  /**
   * Connect an engram to a portal in the same field.
   * Creates activation pathways for cross-field boosting.
   */
  connectToPortal(concept: string, engramId: string, field: 'episodic' | 'self-model', weight = 0.6): void {
    const pair = this.portalPairs.get(concept)
    if (!pair) {
      this.logger.warn('No portal pair found for concept', { concept })
      return
    }

    const portalId = field === 'episodic' ? pair.episodicId : pair.selfModelId
    const targetField = field === 'episodic' ? this.episodicField : this.selfModelField.getField()

    targetField.connect({
      sourceId: engramId,
      targetId: portalId,
      edgeType: 'portal_link',
      weight,
    })
  }

  /**
   * Cross-field retrieval — kindles both fields, boosts portal-connected
   * engrams from each field's top hits, then merges and ranks.
   */
  crossRetrieve(
    query: string,
    options?: KindlingOptions & { limit?: number; preferField?: 'episodic' | 'self-model' },
  ): CrossFieldResult {
    const start = Date.now()
    const limit = options?.limit ?? 12
    const halfLimit = Math.ceil(limit / 2)
    const preferField = options?.preferField

    const episodicHits = this.episodicField.retrieve(query, { ...options, limit: halfLimit })
    const selfModelHits = this.selfModelField.retrieve(query, {
      ...SELF_MODEL_KINDLING_DEFAULTS,
      ...options,
      limit: halfLimit,
    })

    const crossBoosts = this.computeCrossBoosts(episodicHits, selfModelHits)
    const merged = this.mergeResults(episodicHits, selfModelHits, crossBoosts, preferField)
    const hits = merged.slice(0, limit)

    const durationMs = Date.now() - start
    const episodicCount = hits.filter(h => h.sourceField === 'episodic').length
    const selfModelCount = hits.filter(h => h.sourceField === 'self-model').length
    const crossFieldBoostCount = hits.filter(h => h.crossFieldBoosted).length

    this.logger.debug('Cross-field retrieval complete', {
      query: query.slice(0, 80),
      episodicCount,
      selfModelCount,
      crossFieldBoosts: crossFieldBoostCount,
      durationMs,
    })

    return { hits, episodicCount, selfModelCount, crossFieldBoosts: crossFieldBoostCount, durationMs }
  }

  /**
   * Compute cross-field boosts: top hits from each field boost
   * portal-connected engrams in the other field.
   */
  private computeCrossBoosts(
    episodicHits: Array<{ id: string; charge: number }>,
    selfModelHits: Array<{ id: string; charge: number }>,
  ): Map<string, number> {
    const boosts = new Map<string, number>()
    const dampening = this.config.crossFieldDampening
    const pollLimit = this.config.crossPollinationLimit

    for (const hit of selfModelHits.slice(0, pollLimit)) {
      this.boostPortalNeighbors(hit.id, hit.charge, 'self-model', dampening, boosts)
    }

    for (const hit of episodicHits.slice(0, pollLimit)) {
      this.boostPortalNeighbors(hit.id, hit.charge, 'episodic', dampening, boosts)
    }

    return boosts
  }

  /**
   * For an engram, find its portal connections and boost
   * the linked portal's neighbors in the other field.
   */
  private boostPortalNeighbors(
    engramId: string,
    charge: number,
    field: 'episodic' | 'self-model',
    dampening: number,
    boosts: Map<string, number>,
  ): void {
    const concept = this.findPortalConceptForEngram(engramId, field)
    if (!concept) return

    const pair = this.portalPairs.get(concept)
    if (!pair) return

    const otherField = field === 'episodic'
      ? this.selfModelField.getField()
      : this.episodicField
    const otherPortalId = field === 'episodic' ? pair.selfModelId : pair.episodicId

    const { engrams } = otherField.neighbors(otherPortalId)
    for (const neighbor of engrams) {
      const boost = charge * dampening
      const existing = boosts.get(neighbor.id) ?? 0
      boosts.set(neighbor.id, Math.max(existing, boost))
    }
  }

  /**
   * Merge results from both fields, applying cross-boosts and field preference.
   * Field preference uses a score multiplier (not a hard partition).
   */
  private mergeResults(
    episodicHits: MnemicRetrievalHit[],
    selfModelHits: MnemicRetrievalHit[],
    crossBoosts: Map<string, number>,
    preferField?: 'episodic' | 'self-model',
  ): CrossFieldRetrievalHit[] {
    const merged = new Map<string, CrossFieldRetrievalHit>()
    const prefBoost = this.config.fieldPreferenceBoost

    for (const hit of episodicHits) {
      const boost = crossBoosts.get(hit.id) ?? 0
      const prefMultiplier = preferField === 'episodic' ? prefBoost : 1
      merged.set(hit.id, {
        ...hit,
        score: (hit.score + boost) * prefMultiplier,
        charge: hit.charge + boost,
        sourceField: 'episodic',
        crossFieldBoosted: boost > 0,
      })
    }

    for (const hit of selfModelHits) {
      const boost = crossBoosts.get(hit.id) ?? 0
      const prefMultiplier = preferField === 'self-model' ? prefBoost : 1
      const score = (hit.score + boost) * prefMultiplier

      const existing = merged.get(hit.id)
      if (existing && existing.score >= score) continue

      merged.set(hit.id, {
        ...hit,
        score,
        charge: hit.charge + boost,
        sourceField: 'self-model',
        crossFieldBoosted: boost > 0,
      })
    }

    return Array.from(merged.values()).sort((a, b) => b.score - a.score)
  }

  /**
   * Find which portal concept an engram is connected to.
   * Uses reverse index for O(1) portal ID lookup.
   */
  private findPortalConceptForEngram(engramId: string, field: 'episodic' | 'self-model'): string | null {
    const targetField = field === 'episodic' ? this.episodicField : this.selfModelField.getField()
    const { synapses } = targetField.neighbors(engramId)

    for (const syn of synapses) {
      if (syn.edgeType !== 'portal_link') continue
      const portalId = syn.sourceId === engramId ? syn.targetId : syn.sourceId
      const concept = this.portalIdToConcept.get(portalId)
      if (concept) return concept
    }

    return null
  }

  getPortalStats(): Array<{ concept: string; episodicConnections: number; selfModelConnections: number }> {
    const results: Array<{ concept: string; episodicConnections: number; selfModelConnections: number }> = []

    for (const [concept, pair] of this.portalPairs) {
      const epNeighbors = this.episodicField.neighbors(pair.episodicId)
      const smNeighbors = this.selfModelField.getField().neighbors(pair.selfModelId)

      results.push({
        concept,
        episodicConnections: epNeighbors.synapses.filter(s => s.edgeType === 'portal_link').length,
        selfModelConnections: smNeighbors.synapses.filter(s => s.edgeType === 'portal_link').length,
      })
    }

    return results
  }

  /**
   * Rebuild portal pairs from persisted portal engrams on startup.
   */
  rebuildFromPersisted(): number {
    const smField = this.selfModelField.getField()
    const smPortals = smField.list(this.config.maxPortals, 'portal')

    let restored = 0
    for (const portal of smPortals) {
      const meta = portal.metadata as unknown as PortalMetadata
      if (!meta.bridgeConcept || !meta.linkedPortalId || meta.linkedPortalId === 'pending') continue

      const episodicPortal = this.episodicField.get(meta.linkedPortalId)
      if (!episodicPortal) continue

      this.registerPortalPair(meta.bridgeConcept, episodicPortal.id, portal.id)
      restored++
    }

    if (restored > 0) {
      this.logger.info('Restored portal pairs from persisted data', { count: restored })
    }

    return restored
  }

  /**
   * Register a portal pair in both the forward and reverse indexes.
   */
  private registerPortalPair(concept: string, episodicId: string, selfModelId: string): void {
    this.portalPairs.set(concept, { episodicId, selfModelId })
    this.portalIdToConcept.set(episodicId, concept)
    this.portalIdToConcept.set(selfModelId, concept)
  }
}
