import type { PinealStore } from './store.js'
import type { Facet, FacetInput, FacetUpdate, FacetQuery, Domain } from './types.js'
import { REINFORCEMENT_RATE } from './types.js'
import type { ILogger } from '@cassicore/foundation'
import type { MnemicField } from '@cassicore/mnemic-field'
import type { Engram } from '@cassicore/mnemic-field'
import { buildPinealMetadata } from './index.js'

export class FacetManager {
  private pinealEngramMap = new Map<string, string>()  // facetId → engramId

  constructor(
    private store: PinealStore,
    private logger: ILogger,
    private mnemicField: MnemicField | null = null,
  ) {}

  /** Find the MnemicField engram for a facet. */
  private findEngram(facetId: string): Engram | null {
    if (!this.mnemicField) return null
    const cached = this.pinealEngramMap.get(facetId)
    if (cached) {
      const engram = this.mnemicField.get(cached)
      if (engram) return engram
      this.pinealEngramMap.delete(facetId)
    }
    const matches = this.mnemicField.searchByProvenance(`pineal:${facetId}`)
    if (matches.length > 0) {
      this.pinealEngramMap.set(facetId, matches[0].id)
      return matches[0]
    }
    return null
  }

  /** Sync a facet to its MnemicField engram (create or update). Best-effort — never throws. */
  private syncToField(facet: Facet): void {
    if (!this.mnemicField) return
    try {
      const existing = this.findEngram(facet.id)
      if (existing) {
        this.mnemicField.update(existing.id, {
          content: facet.content,
          metadata: { ...existing.metadata, ...buildPinealMetadata(facet) },
          tags: [...new Set(['pineal', facet.domain, facet.category, ...(facet.tags ?? []), ...(existing.tags ?? [])])],
        })
      } else {
        const engram = this.mnemicField.store({
          content: facet.content,
          nodeType: 'pineal_facet' as import('@cassicore/mnemic-field').EngramType,
          x: 0,
          y: 0,
          provenance: `pineal:${facet.id}`,
          tags: ['pineal', facet.domain, facet.category, ...(facet.tags ?? [])],
          metadata: buildPinealMetadata(facet),
        })
        this.pinealEngramMap.set(facet.id, engram.id)
      }
    } catch (err) {
      this.logger.warn('[pineal] Failed to sync facet to MnemicField', {
        facetId: facet.id,
        error: String(err),
      })
    }
  }

  create(input: FacetInput): Facet {
    const facet = this.store.create(input)
    this.logger.info('[pineal] Facet created', {
      id: facet.id,
      domain: facet.domain,
      category: facet.category,
      conviction: facet.conviction,
    })
    this.syncToField(facet)
    return facet
  }

  get(id: string): Facet | null {
    return this.store.get(id)
  }

  update(id: string, updates: FacetUpdate): Facet | null {
    const facet = this.store.update(id, updates)
    if (facet) {
      this.logger.debug('[pineal] Facet updated', { id, updates: Object.keys(updates) })
      this.syncToField(facet)
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
      this.syncToField(updated)
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
      // Sync new evolved facet to field at origin
      this.syncToField(evolved)
      // Retire old facet's field engram
      const oldEngram = this.findEngram(id)
      if (oldEngram && this.mnemicField) {
        this.mnemicField.update(oldEngram.id, {
          metadata: { ...oldEngram.metadata, active: false },
          tags: [...new Set([...(oldEngram.tags ?? []), 'retired'])],
        })
        this.pinealEngramMap.delete(id)
      }
    }
    return evolved
  }

  retire(id: string): boolean {
    const result = this.store.retire(id)
    if (result) {
      this.logger.info('[pineal] Facet retired', { id })
      const engram = this.findEngram(id)
      if (engram && this.mnemicField) {
        this.mnemicField.update(engram.id, {
          metadata: { ...engram.metadata, active: false },
          tags: [...new Set([...(engram.tags ?? []), 'retired'])],
        })
        this.pinealEngramMap.delete(id)
      }
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
   */
  setConviction(id: string, conviction: number): Facet | null {
    const clamped = Math.max(0, Math.min(1, conviction))
    const facet = this.store.update(id, { conviction: clamped })
    if (facet) this.syncToField(facet)
    return facet
  }

  pin(id: string): boolean {
    const result = this.store.pin(id, true)
    if (result) {
      this.logger.info('[pineal] Facet pinned', { id })
      const facet = this.store.get(id)
      if (facet) this.syncToField(facet)
    }
    return result
  }

  unpin(id: string): boolean {
    const result = this.store.pin(id, false)
    if (result) {
      this.logger.info('[pineal] Facet unpinned', { id })
      const facet = this.store.get(id)
      if (facet) this.syncToField(facet)
    }
    return result
  }
}
