import type { PinealStore } from './store.js'
import type { Facet, SkillSummary } from './types.js'
import type { ILogger } from '../../../types/interfaces.js'

/**
 * SkillLoader — composes praxis facets into coherent skill prompts on demand.
 *
 * Unlike other domains (which are contextually injected every turn),
 * praxis facets are loaded explicitly when a skill is invoked.
 */
export class SkillLoader {
  constructor(
    private store: PinealStore,
    private logger: ILogger,
  ) {}

  /**
   * Load a skill by name — composes all active praxis facets
   * for that category into a coherent instruction prompt.
   * Facets are ordered by salience descending, then conviction descending.
   */
  loadSkill(name: string): string | null {
    const facets = this.store.list({
      domain: 'praxis',
      category: name,
      active: true,
    })

    if (facets.length === 0) {
      this.logger.debug('[skill-loader] Skill not found', { name })
      return null
    }

    const lines = facets.map(f => f.content)
    const composed = lines.join('\n\n')

    this.logger.debug('[skill-loader] Loaded skill', {
      name,
      facets: facets.length,
      chars: composed.length,
    })

    return composed
  }

  /**
   * List all available skills with metadata.
   */
  listSkills(): SkillSummary[] {
    return this.store.getSkillSummaries()
  }

  /**
   * Get the IDs of all facets for a skill (for reinforcement after use).
   */
  getSkillFacetIds(name: string): string[] {
    const facets = this.store.list({
      domain: 'praxis',
      category: name,
      active: true,
    })
    return facets.map(f => f.id)
  }
}
