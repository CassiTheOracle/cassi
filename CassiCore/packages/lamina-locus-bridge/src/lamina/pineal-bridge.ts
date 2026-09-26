/**
 * pineal-bridge.ts — Mirror Pineal facets into read-only laminae.
 *
 * The Lamina substrate becomes the single injection surface for Cassi's
 * curated state. Pineal remains the source of truth for identity/wisdom,
 * but its high-conviction facets are projected as read-only laminae so
 * they participate in the same injection pipeline as primary-edited blocks.
 *
 * Idempotent: safe to call repeatedly (e.g. after every Pineal update).
 */

import type { ILogger } from '@cassicore/foundation'
import type { LaminaField } from './lamina-field.js'
import type { Domain, Facet } from '../vendor/core/intelligence/pineal/types.js'

export interface PinealLike {
  listFacets(query?: { active?: boolean; minConviction?: number; domain?: Domain; limit?: number }): Facet[]
}

const DOMAINS: Domain[] = ['identity', 'wisdom', 'philosophy']
const MIN_CONVICTION = 0.6
const PER_DOMAIN_CHAR_BUDGET = 6_000

function renderDomain(facets: Facet[]): string {
  return facets
    .map(f => `- (${f.category}, conviction ${f.conviction.toFixed(2)}) ${f.content}`)
    .join('\n')
}

export class PinealLaminaBridge {
  constructor(
    private readonly pineal: PinealLike,
    private readonly lamina: LaminaField,
    private readonly logger: ILogger,
  ) {}

  /** Project current Pineal facets into per-domain read-only laminae. Returns labels updated. */
  syncOnce(): string[] {
    const updated: string[] = []
    for (const domain of DOMAINS) {
      try {
        const facets = this.pineal
          .listFacets({ active: true, domain, minConviction: MIN_CONVICTION, limit: 100 })
          .sort((a, b) => b.conviction - a.conviction)
        if (facets.length === 0) continue

        let body = renderDomain(facets)
        if (body.length > PER_DOMAIN_CHAR_BUDGET) {
          body = body.slice(0, PER_DOMAIN_CHAR_BUDGET) + '\n[truncated]'
        }
        const label = `pineal:${domain}`
        this.lamina.mirrorReadOnly({
          label,
          content: body,
          owner: 'pineal',
          description: `Active ${domain} facets above ${MIN_CONVICTION} conviction. Mirrored from Pineal — read-only.`,
          tags: ['pineal', domain, 'mirror'],
          charLimit: PER_DOMAIN_CHAR_BUDGET + 256,
        })
        updated.push(label)
      } catch (err) {
        this.logger.debug?.(`[pineal-bridge] sync failed for domain ${domain}`, { error: String(err) })
      }
    }
    if (updated.length > 0) {
      this.logger.info?.('[pineal-bridge] synced facets to laminae', { domains: updated })
    }
    return updated
  }
}
