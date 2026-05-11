import type { PinealStore } from './store.js'
import type { Facet, FacetInput, FacetUpdate, FacetQuery, Domain } from './types.js'
import { REINFORCEMENT_RATE } from './types.js'
import type { ILogger } from '../../../types/interfaces.js'
import type { MnemicField } from '../mnemic-field/index.js'

export class FacetManager {
  constructor(
    private store: PinealStore,
    private logger: ILogger,
    private mnemicField: MnemicField | null = null,
  ) {}

  create(input: FacetInput): Facet {
    const facet = this.store.create(input)
    this.logger.info('[pineal] Facet created', {
      id: facet.id,
      domain: facet.domain,
      category: facet.category,
      conviction: facet.conviction,
    })
    if (this.mnemicField) {
      this.mnemicField.store({
        id: `pineal:${facet.id}`,
        content: facet.content,
        nodeType: 'expert_summary' as const,
        provenance: 'pineal',
        metadata: {
          expertId: facet.id,
          expertKind: facet.domain === 'identity' ? 'identity' : facet.domain === 'wisdom' ? 'meta_cognitive' : facet.domain === 'philosophy' ? 'principle' : 'skill',
          expertDomain: facet.domain,
          expertConviction: facet.conviction,
          expertPinned: facet.pinned,
          expertScope: facet.scope,
          expertVersion: facet.version,
          expertProvenance: 'soul.md',
          expertLastReinforced: new Date().toISOString(),
          expertReinforcements: 0,
          expertSourceIds: [],
        },
      })
    }
    return facet
  }

  get(id: string): Facet | null {
    return this.store.get(id)
  }

  update(id: string, updates: FacetUpdate): Facet | null {
    const facet = this.store.update(id, updates)
    if (facet) {
      this.logger.debug('[pineal] Facet updated', { id, updates: Object.keys(updates) })
    }
    return facet
  }

  /**
   * Reinforce a facet after successful use.
   * Applies asymptotic growth: +REINFORCEMENT_RATE × (1 - conviction)
   * This produces rapid early growth and diminishing returns near the ceiling.
   */
  reinforce(id: string): Facet | null {
    const facet = this.store.get(id)
    if (!facet || !facet.active) return null

    const increment = REINFORCEMENT_RATE * (1 - facet.conviction)
    const newConviction = Math.min(1, facet.conviction + increment)

    const updated = this.store.reinforce(id, newConviction)
    if (updated) {
      this.logger.debug('[pineal] Facet reinforced', {
        id,
        domain: facet.domain,
        prev: facet.conviction.toFixed(3),
        now: newConviction.toFixed(3),
        delta: `+${increment.toFixed(4)}`,
        reinforcements: updated.reinforcements,
      })
    }
    return updated
  }

  /**
   * Reinforce all facets used in a turn.
   * Returns the number of facets reinforced.
   */
  reinforceMany(ids: string[]): number {
    let count = 0
    for (const id of ids) {
      if (this.reinforce(id)) count++
    }
    return count
  }

  /**
   * Evolve a facet — create a new version with updated content.
   * The old facet is retired; the new one starts at domain initial conviction.
   */
  evolve(id: string, newContent: string, input?: Partial<FacetInput>): Facet | null {
    const evolved = this.store.evolve(id, newContent, input)
    if (evolved) {
      this.logger.info('[pineal] Facet evolved', {
        originalId: id,
        newId: evolved.id,
        domain: evolved.domain,
        version: evolved.version,
      })
    }
    return evolved
  }

  retire(id: string): boolean {
    const result = this.store.retire(id)
    if (result) {
      this.logger.info('[pineal] Facet retired', { id })
    }
    return result
  }

  list(query?: FacetQuery): Facet[] {
    return this.store.list(query)
  }

  listByDomain(domain: Domain): Facet[] {
    return this.store.list({ domain, active: true })
  }

  getHistory(facetId: string): Facet[] {
    return this.store.getHistory(facetId)
  }

  /**
   * Explicitly set conviction (bypass organic growth).
   * Used by Valerie or meditation to directly assert conviction.
   */
  setConviction(id: string, conviction: number): Facet | null {
    const clamped = Math.max(0, Math.min(1, conviction))
    return this.store.update(id, { conviction: clamped })
  }

  /**
   * Pin a facet — guarantees it will always be included in the assembled
   * pineal injection, exempt from budget constraints.
   */
  pin(id: string): boolean {
    const result = this.store.pin(id, true)
    if (result) {
      this.logger.info('[pineal] Facet pinned', { id })
    }
    return result
  }

  /**
   * Unpin a facet — returns it to normal budget-constrained assembly.
   */
  unpin(id: string): boolean {
    const result = this.store.pin(id, false)
    if (result) {
      this.logger.info('[pineal] Facet unpinned', { id })
    }
    return result
  }
}
