import type { PinealStore } from './store.js'
import type { Facet, SkillSummary } from './types.js'
import type { ILogger } from '../../../types/interfaces.js'

/**
 * PinealAssembler — selects and formats relevant facets for context injection.
 *
 * Assembly strategy:
 *   1. Always include all active identity facets (core self)
 *   2. Include wisdom facets ranked by conviction (operational knowledge)
 *   3. Include high-conviction philosophy facets (established beliefs)
 *   4. Append skills index as compact comma-separated list
 *   5. Respect character budget
 *
 * Output is natural language prose grouped by domain, not bullet lists.
 * Higher-conviction facets appear first within each domain (store already sorts by conviction DESC).
 * Praxis facets are NOT included — they're loaded on demand via SkillLoader.
 */
export class PinealAssembler {
  constructor(
    private store: PinealStore,
    private logger: ILogger,
    private charBudget: number = 4_500,
  ) {}

  /**
   * Assemble relevant facets for a turn injection.
   * Returns formatted natural language text ready for `<pineal>` wrapping.
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
    if (skills.length > 0 && remaining > 60) {
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

    const header = `[${label}]\n`
    let text = header
    const ids: string[] = []

    for (const facet of facets) {
      const sentence = facet.content.endsWith('.') || facet.content.endsWith('?') || facet.content.endsWith('!')
        ? `${facet.content} `
        : `${facet.content}. `

      if (text.length + sentence.length > budget) break
      text += sentence
      ids.push(facet.id)
    }

    if (ids.length === 0) return { text: '', ids: [] }

    return { text: text.trimEnd(), ids }
  }

  private formatSkillsIndex(skills: SkillSummary[], budget: number): string | null {
    const names = skills.map(s => s.name)
    const line = `[Skills] ${names.join(', ')}`
    if (line.length > budget) {
      const truncated = line.slice(0, budget - 3) + '...'
      return truncated
    }
    return line
  }
}
