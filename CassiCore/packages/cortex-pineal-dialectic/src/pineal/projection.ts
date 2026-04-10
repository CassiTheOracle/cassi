import type { PinealStore } from './store.js'
import type { Facet } from './types.js'
import type { ILogger } from '../../../types/interfaces.js'

/**
 * Cortex projection interface — matches CorticalField.signal() signature.
 * Avoids importing the full Cortex to keep the Pineal loosely coupled.
 */
interface CortexProjectionTarget {
  signal(region: string, input: {
    type: string
    content: string
    author: string
    salience?: number
    tags?: string[]
    decayRate?: number
  }): unknown
}

const PROJECTION_REGION = 'executive'
const PROJECTION_AUTHOR = 'pineal'
const PROJECTION_DECAY_RATE = 0.01
const MIN_CONVICTION_FOR_PROJECTION = 0.4

/**
 * PinealProjection — projects high-conviction identity facets into the Cortex
 * as persistent "tonic" signals in the executive region.
 *
 * These signals provide a stable identity presence in the Cortex's dynamic
 * signal space, refreshed periodically to counteract minimal decay.
 */
export class PinealProjection {
  private projectedIds = new Set<string>()

  constructor(
    private store: PinealStore,
    private logger: ILogger,
  ) {}

  /**
   * Project identity facets into the Cortex.
   * Selects active identity facets above the conviction threshold.
   */
  project(cortex: CortexProjectionTarget): number {
    const facets = this.store.list({
      domain: 'identity',
      active: true,
      minConviction: MIN_CONVICTION_FOR_PROJECTION,
    })

    let projected = 0
    for (const facet of facets) {
      try {
        cortex.signal(PROJECTION_REGION, {
          type: 'insight',
          content: facet.content,
          author: PROJECTION_AUTHOR,
          salience: facet.conviction,
          tags: ['pineal', 'identity', facet.category],
          decayRate: PROJECTION_DECAY_RATE,
        })
        this.projectedIds.add(facet.id)
        projected++
      } catch (err) {
        this.logger.warn('[pineal-projection] Failed to project facet', {
          facetId: facet.id,
          error: String(err),
        })
      }
    }

    if (projected > 0) {
      this.logger.debug('[pineal-projection] Projected identity facets', {
        projected,
        total: facets.length,
      })
    }

    return projected
  }

  /**
   * Refresh projections — call during oscillation ticks to keep
   * identity signals alive in the Cortex despite minimal decay.
   */
  refresh(cortex: CortexProjectionTarget): number {
    return this.project(cortex)
  }

  getProjectedCount(): number {
    return this.projectedIds.size
  }
}
