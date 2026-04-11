import type { InjectionSource } from '../injection-aggregator.js'
import type { PinealAssembler } from './assembler.js'
import type { FacetManager } from './facet.js'
import type { ILogger } from '../../../types/interfaces.js'

/**
 * PinealInjectionSource — provides identity/wisdom/philosophy context to the InjectionAggregator.
 *
 * Registered at boot with priority 9 (high — identity is foundational context).
 * Reinforces all facets that were included in the injection after a successful turn.
 */
export class PinealInjectionSource implements InjectionSource {
  readonly name = 'pineal'
  readonly priority = 9

  private lastInjectedFacetIds: string[] = []

  constructor(
    private assembler: PinealAssembler,
    private facetManager: FacetManager,
    private logger: ILogger,
  ) {}

  async getInjection(sessionId: string): Promise<string | null> {
    const { text, facetIds } = this.assembler.assemble(sessionId)

    if (!text) return null

    this.lastInjectedFacetIds = facetIds

    return `<pineal>\n${text}\n</pineal>`
  }

  /**
   * Called after a successful turn to reinforce all facets that were used.
   * This is the organic growth mechanism — facets earn conviction through use.
   */
  reinforceLastInjection(): number {
    if (this.lastInjectedFacetIds.length === 0) return 0

    const count = this.facetManager.reinforceMany(this.lastInjectedFacetIds)
    this.logger.debug('[pineal-injection] Reinforced facets from last turn', {
      reinforced: count,
      total: this.lastInjectedFacetIds.length,
    })

    this.lastInjectedFacetIds = []
    return count
  }

  getLastInjectedIds(): string[] {
    return [...this.lastInjectedFacetIds]
  }
}
