import type { PinealStore } from './store.js'
import type { Facet, SkillSummary } from './types.js'
import { channelFromSessionId } from './types.js'
import type { ILogger } from '../../../types/interfaces.js'

/**
 * PinealAssembler — selects and formats relevant facets for context injection.
 *
 * Assembly strategy:
 *   1. Always include pinned facets (guaranteed inclusion, exempt from budget)
 *   2. Include remaining active identity facets (core self)
 *   3. Include remaining wisdom facets ranked by conviction (operational knowledge)
 *   4. Include remaining philosophy facets ranked by conviction (established beliefs)
 *   5. Append skills index as compact comma-separated list
 *   6. Non-pinned facets respect the character budget
 *
 * Channel-scoped facets: facets with a `scope` matching the session's channel
 * are included alongside universal (scope=null) facets. Scoped facets from other
 * channels are excluded. This enables per-integration behavior rules (e.g.,
 * "prefer the question tool" for OpenCode) managed through the Pineal lifecycle.
 *
 * Within each domain, the store returns pinned facets first, then by conviction DESC.
 * Output is natural language prose grouped by domain, not bullet lists.
 * Praxis facets are NOT included — they're loaded on demand via SkillLoader.
 */
export class PinealAssembler {
  constructor(
    private store: PinealStore,
    private logger: ILogger,
    private charBudget: number = 8_000,
  ) {}

  /**
   * Assemble relevant facets for a turn injection.
   * Returns formatted natural language text ready for `<pineal>` wrapping.
   *
   * @param sessionId — used to determine channel for scope filtering
   * @param channel — explicit channel override (takes precedence over sessionId prefix)
   */
  assemble(sessionId?: string, channel?: string | null): { text: string; facetIds: string[] } {
    const resolvedChannel = channel ?? channelFromSessionId(sessionId)
    const facetIds: string[] = []
    const sections: string[] = []
    let remaining = this.charBudget

    // matchScope: include universal (scope=null) + channel-specific facets
    const queryBase = { active: true as const, matchScope: resolvedChannel }

    const identity = this.store.list({ ...queryBase, domain: 'identity' })
    const identitySection = this.formatDomain('Identity', identity, remaining)
    if (identitySection.text) {
      sections.push(identitySection.text)
      remaining -= identitySection.text.length
      facetIds.push(...identitySection.ids)
    }

    const wisdom = this.store.list({ ...queryBase, domain: 'wisdom' })
    const wisdomSection = this.formatDomain('Wisdom', wisdom, remaining)
    if (wisdomSection.text) {
      sections.push(wisdomSection.text)
      remaining -= wisdomSection.text.length
      facetIds.push(...wisdomSection.ids)
    }

    const philosophy = this.store.list({ ...queryBase, domain: 'philosophy' })
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

    if (resolvedChannel) {
      this.logger.debug('[pineal-assembler] Assembled with channel scope', {
        channel: resolvedChannel,
        facetCount: facetIds.length,
      })
    }

    return {
      text: sections.join('\n\n'),
      facetIds,
    }
  }

  /**
   * Format a domain section. Pinned facets are always included (exempt from budget).
   * Non-pinned facets fill remaining budget by conviction order.
   * Store already returns facets sorted: pinned DESC, conviction DESC, salience DESC.
   */
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

      if (facet.pinned) {
        text += sentence
        ids.push(facet.id)
      } else {
        if (text.length + sentence.length > budget) break
        text += sentence
        ids.push(facet.id)
      }
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
