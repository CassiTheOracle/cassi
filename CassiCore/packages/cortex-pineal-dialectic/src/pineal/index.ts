import { BaseCognitiveModule } from '../base/cognitive-module.js'
import { PinealStore } from './store.js'
import { FacetManager } from './facet.js'
import { SkillLoader } from './skill-loader.js'
import { parseAllSkillFiles } from './skill-parser.js'
import { SEED_FACETS, CHANNEL_SEED_FACETS } from './seed.js'

import type { ILogger } from '../../../types/interfaces.js'
import type { Facet, FacetInput, FacetUpdate, FacetQuery, Domain, DomainStats, PinealSnapshot, SkillSummary } from './types.js'
import type { MnemicField } from '../mnemic-field/index.js'

/** Build metadata for a Pineal facet engram — shared between seeding and CRUD sync. */
export function buildPinealMetadata(facet: Facet): Record<string, unknown> {
  return {
    pinealId: facet.id,
    domain: facet.domain,
    category: facet.category,
    conviction: facet.conviction,
    salience: facet.salience,
    pinned: facet.pinned,
    scope: facet.scope,
    version: facet.version,
    provenance: facet.provenance,
    active: facet.active,
    createdAt: facet.createdAt,
    lastReinforced: facet.lastReinforced,
    reinforcements: facet.reinforcements,
  }
}

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
   * Mirror all active Pineal facets into the MnemicField as engrams at (0, 0).
   * This is the foundation of the radial/polar topology — the Pineal's identity
   * facets become the tonic center of the field's attention.
   *
   * Idempotent: checks for existing engrams with matching pineal provenance
   * before creating. Safe to call on every boot.
   *
   * Returns the number of new engrams created.
   */
  seedMnemicFieldFacets(): number {
    if (!this.mnemicField) return 0

    const facets = this.store.list({ active: true })
    if (facets.length === 0) return 0

    // Batch-check which facets already exist in the field
    const existingProvenances = new Set<string>()
    const allEngrams = this.mnemicField.list(10000)
    for (const e of allEngrams) {
      const prov = e.provenance ?? ''
      if (prov.startsWith('pineal:')) {
        existingProvenances.add(prov)
      }
    }

    let created = 0
    for (const facet of facets) {
      const provenance = `pineal:${facet.id}`
      if (existingProvenances.has(provenance)) continue

      this.mnemicField.store({
        content: facet.content,
        nodeType: 'pineal_facet' as import('../mnemic-field/types.js').EngramType,
        x: 0,
        y: 0,
        provenance,
        tags: ['pineal', facet.domain, facet.category, ...(facet.tags ?? [])],
        metadata: buildPinealMetadata(facet),
      })
      existingProvenances.add(provenance)
      created++
    }

    if (created > 0) {
      this.logger.info('[pineal] Seeded facets into MnemicField at origin', {
        created,
        total: facets.length,
      })
    }

    return created
  }

  /**
   * Reconcile PinealStore from MnemicField — reads all pineal_facet engrams
   * from the field and updates PinealStore entries where the field has newer
   * content or conviction. Used on boot to recover from field-first state
   * (e.g. after a rebuild). Does NOT create new facets — seeding handles that.
   *
   * Returns the number of facets updated from the field.
   */
  reconcileFromField(): number {
    if (!this.mnemicField) return 0

    const fieldFacets = this.mnemicField.list(10000).filter(
      e => e.nodeType === 'pineal_facet' && (e.provenance ?? '').startsWith('pineal:'),
    )

    let synced = 0
    for (const engram of fieldFacets) {
      const pinealId = (engram.metadata as any)?.pinealId as string | undefined
      if (!pinealId) continue

      const existing = this.store.get(pinealId)
      if (!existing) continue  // Not in store — seeding will handle creation

      const fieldConviction = (engram.metadata as any)?.conviction as number | undefined
      if (existing.content !== engram.content || (fieldConviction !== undefined && existing.conviction !== fieldConviction)) {
        this.store.update(pinealId, {
          content: engram.content,
          conviction: fieldConviction,
        })
        synced++
      }
    }

    if (synced > 0) {
      this.logger.info('[pineal] Reconciled facets from MnemicField', {
        synced,
        fieldTotal: fieldFacets.length,
      })
    }

    return synced
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
