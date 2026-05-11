import { BaseCognitiveModule } from '../base/cognitive-module.js'
import { PinealStore } from './store.js'
import { FacetManager } from './facet.js'
import { SkillLoader } from './skill-loader.js'
import { parseAllSkillFiles } from './skill-parser.js'
import { SEED_FACETS, CHANNEL_SEED_FACETS } from './seed.js'

import type { ILogger } from '../../../types/interfaces.js'
import type { Facet, FacetInput, FacetUpdate, FacetQuery, Domain, DomainStats, PinealSnapshot, SkillSummary } from './types.js'
import type { MnemicField } from '../mnemic-field/index.js'

export class PinealModule extends BaseCognitiveModule {
  readonly name = 'pineal'
  readonly priority = 90

  private store!: PinealStore
  private facets!: FacetManager
  private skills!: SkillLoader
  private mnemicField: MnemicField | null = null

  setMnemicField(mf: MnemicField): void { this.mnemicField = mf }

  constructor(logger: ILogger) {
    super(logger)
  }

  async init(): Promise<void> {
    await super.init()

    this.store = new PinealStore(this.logger)
    this.facets = new FacetManager(this.store, this.logger, this.mnemicField)
    this.skills = new SkillLoader(this.store, this.logger)

    // Seed channel-scoped facets on every boot (additive, idempotent by content)
    this.seedChannelFacets()

    const count = this.store.countActive()
    this.logger.info('[pineal] Initialized', { activeFacets: count })
  }

  async stop(): Promise<void> {
    this.store.close()
    await super.stop()
  }

  createFacet(input: FacetInput): Facet {
    return this.facets.create(input)
  }

  getFacet(id: string): Facet | null {
    return this.facets.get(id)
  }

  updateFacet(id: string, updates: FacetUpdate): Facet | null {
    return this.facets.update(id, updates)
  }

  reinforceFacet(id: string): Facet | null {
    return this.facets.reinforce(id)
  }

  reinforceMany(ids: string[]): number {
    return this.facets.reinforceMany(ids)
  }

  evolveFacet(id: string, newContent: string, input?: Partial<FacetInput>): Facet | null {
    return this.facets.evolve(id, newContent, input)
  }

  retireFacet(id: string): boolean {
    return this.facets.retire(id)
  }

  setConviction(id: string, conviction: number): Facet | null {
    return this.facets.setConviction(id, conviction)
  }

  pinFacet(id: string): boolean {
    return this.facets.pin(id)
  }

  unpinFacet(id: string): boolean {
    return this.facets.unpin(id)
  }

  listFacets(query?: FacetQuery): Facet[] {
    return this.facets.list(query)
  }

  listByDomain(domain: Domain): Facet[] {
    return this.facets.listByDomain(domain)
  }

  getFacetHistory(facetId: string): Facet[] {
    return this.facets.getHistory(facetId)
  }

  getDomainStats(): DomainStats[] {
    return this.store.getDomainStats()
  }

  getSkillSummaries(): SkillSummary[] {
    return this.store.getSkillSummaries()
  }

  getSnapshot(): PinealSnapshot {
    return {
      facets: this.facets.list({ active: true }),
      domains: this.getDomainStats(),
      timestamp: new Date().toISOString(),
    }
  }

  countActive(domain?: Domain): number {
    return this.store.countActive(domain)
  }

  /**
   * Seed the Pineal with initial facets from SOUL.md, AGENTS.md, and philosophy.
   * Idempotent — skips if facets already exist.
   * Returns the number of facets created.
   */
  seed(): number {
    const existing = this.store.countActive()
    if (existing > 0) {
      this.logger.info('[pineal] Seed skipped — facets already exist', { count: existing })
      return 0
    }

    let created = 0
    for (const input of SEED_FACETS) {
      this.facets.create(input)
      created++
    }

    this.logger.info('[pineal] Seeded initial facets', {
      created,
      identity: SEED_FACETS.filter(f => f.domain === 'identity').length,
      wisdom: SEED_FACETS.filter(f => f.domain === 'wisdom').length,
      philosophy: SEED_FACETS.filter(f => f.domain === 'philosophy').length,
    })

    return created
  }

  /**
   * Seed channel-scoped facets for client integrations.
   * Unlike seed(), this is additive — it checks for duplicates by content+scope
   * and only creates missing facets. Safe to call on every boot.
   * Returns the number of facets created.
   */
  seedChannelFacets(): number {
    let created = 0

    for (const input of CHANNEL_SEED_FACETS) {
      // Check if a facet with the same content+scope already exists
      const existing = this.store.list({
        domain: input.domain,
        category: input.category,
        active: true,
        scope: input.scope ?? null,
      })

      const duplicate = existing.find(f => f.content === input.content)
      if (duplicate) continue

      this.facets.create(input)
      created++
    }

    if (created > 0) {
      this.logger.info('[pineal] Seeded channel-scoped facets', { created })
    }

    return created
  }

  /**
   * Parse skill files from skill directories into praxis facets.
   * Idempotent by skill category — re-parsing retires old facets and creates new ones.
   */
  parseSkills(skillDirs: string[]): number {
    const inputs = parseAllSkillFiles(skillDirs, this.logger)
    if (inputs.length === 0) return 0

    const existingSkills = new Set(
      this.store.list({ domain: 'praxis', active: true }).map(f => f.category)
    )

    let created = 0
    for (const input of inputs) {
      if (existingSkills.has(input.category)) {
        const existing = this.store.list({ domain: 'praxis', category: input.category, active: true })
        const match = existing.find(f => f.tags.join(',') === (input.tags ?? []).join(','))
        if (match) continue
      }
      this.facets.create(input)
      created++
    }

    this.logger.info('[pineal] Parsed skill files', {
      created,
      skills: new Set(inputs.map(f => f.category)).size,
    })

    return created
  }

  loadSkill(name: string): string | null {
    return this.skills.loadSkill(name)
  }

  listSkills(): SkillSummary[] {
    return this.skills.listSkills()
  }

  getSkillFacetIds(name: string): string[] {
    return this.skills.getSkillFacetIds(name)
  }

  /**
   * Access the FacetManager directly for advanced operations.
   * Prefer the named methods above for standard use.
   */
  getFacetManager(): FacetManager {
    return this.facets
  }

  /**
   * Access the store directly for operations not exposed on the manager.
   */
  getStore(): PinealStore {
    return this.store
  }
}

export type { Facet, FacetInput, FacetUpdate, FacetQuery, Domain, DomainStats, PinealSnapshot, SkillSummary } from './types.js'
export { DOMAINS, DOMAIN_INITIAL_CONVICTION, REINFORCEMENT_RATE, CHANNEL_PREFIXES, channelFromSessionId } from './types.js'
