import type { PinealStore } from './store.js'
import type { Facet, Domain, SkillSummary } from './types.js'
import type { ILogger } from '../../../types/interfaces.js'

/**
 * PinealAssembler — selects and formats relevant facets for context injection.
 *
 * Assembly strategy:
 *   1. Always include all active identity facets (core self)
 *   2. Include wisdom facets ranked by conviction (operational knowledge)
 *   3. Include high-conviction philosophy facets (established beliefs)
 *   4. Append skills index (praxis names + descriptions only, not full content)
 *   5. Respect character budget
 *
 * Praxis facets are NOT included — they're loaded on demand via SkillLoader.
 */
export class PinealAssembler {
  constructor(
    private store: PinealStore,
    private logger: ILogger,
    private charBudget: number = 6_000,
  ) {}

  /**
   * Assemble relevant facets for a turn injection.
   * Returns formatted text ready for `<cassi-pineal>` wrapping.
   */
  assemble(_sessionId?: string): { text: string; facetIds: string[] } {
    const facetIds: string[] = []
    const sections: string[] = []
    let remaining = this.charBudget

    const identity = this.store.list({ domain: 'identity', active: true })
    const identitySection = this.formatDomain('Identity', identity, remaining)
    if (identitySection.text) {
      sections.push(identitySection.text)
      remaining -= identitySection.text.length
      facetIds.push(...identitySection.ids)
    }

    const wisdom = this.store.list({ domain: 'wisdom', active: true })
    const wisdomSection = this.formatDomain('Wisdom', wisdom, remaining)
    if (wisdomSection.text) {
      sections.push(wisdomSection.text)
      remaining -= wisdomSection.text.length
      facetIds.push(...wisdomSection.ids)
    }

    const philosophy = this.store.list({ domain: 'philosophy', active: true })
    const philSection = this.formatDomain('Philosophy', philosophy, remaining)
    if (philSection.text) {
      sections.push(philSection.text)
      remaining -= philSection.text.length
      facetIds.push(...philSection.ids)
    }

    const skills = this.store.getSkillSummaries()
    if (skills.length > 0 && remaining > 100) {
      const skillsIndex = this.formatSkillsIndex(skills, remaining)
      if (skillsIndex) {
        sections.push(skillsIndex)
      }
    }

    return {
      text: sections.join('\n\n'),
      facetIds,
    }
  }

  private formatDomain(
    label: string,
    facets: Facet[],
    budget: number,
  ): { text: string; ids: string[] } {
    if (facets.length === 0) return { text: '', ids: [] }

    const header = `[${label}]`
    let text = header
    const ids: string[] = []

    for (const facet of facets) {
      const line = `\n- ${facet.content}`
      if (text.length + line.length > budget) break
      text += line
      ids.push(facet.id)
    }

    if (ids.length === 0) return { text: '', ids: [] }

    return { text, ids }
  }

  private formatSkillsIndex(skills: SkillSummary[], budget: number): string | null {
    let text = '[Available Skills]'

    for (const skill of skills) {
      const line = `\n- ${skill.name}: ${skill.description || `(${skill.facetCount} facets)`}`
      if (text.length + line.length > budget) break
      text += line
    }

    return text.length > '[Available Skills]'.length ? text : null
  }
}
