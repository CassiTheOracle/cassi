import path from 'node:path'
import type { ILogger } from '../../../../types/interfaces.js'
import { getDataDir } from '../../../utils/paths.js'
import { MnemicField } from '../index.js'
import type {
  Engram, EngramUpdate, MnemicRetrievalHit, KindlingOptions,
  EngramType, SynapseType, MnemicSynapse, FieldStats,
} from '../types.js'
import {
  SELF_MODEL_ENGRAM_TYPES, SELF_MODEL_KINDLING_DEFAULTS,
  type ModuleMetadata, type CapabilityMetadata, type PatternMetadata,
  type WeaknessMetadata, type EvolutionMetadata, type PortalMetadata,
} from './types.js'

/**
 * Mapping from self-model engram types to the metadata key used for
 * automatic tag generation when storing engrams.
 */
const TAG_EXTRACTORS: Record<string, (meta: Record<string, unknown>) => string[]> = {
  module: (m) => [m.domain as string].filter(Boolean),
  capability: () => [],
  pattern: (m) => [m.category as string].filter(Boolean),
  principle: () => [],
  weakness: (m) => [m.severity as string].filter(Boolean),
  evolution: (m) => [m.changeType as string].filter(Boolean),
}

/**
 * The Self-Model Field — a second Mnemic Field that stores semantic
 * understanding of the codebase architecture rather than episodic memory.
 *
 * While the episodic field stores what happened ("I debugged the kindling bug"),
 * the Self-Model Field stores what things ARE ("The Kindling Engine uses
 * spreading activation to retrieve memories associatively").
 *
 * It uses the same MnemicField infrastructure (Cortex, FilamentCortex,
 * KindlingEngine, R-tree, FTS5) but with different kindling defaults:
 * - Uses 'complex' complexity for the lowest spark point modifier (0.7)
 * - Filaments always enabled for precision retrieval
 *
 * The field is connected to the episodic field via an InterFieldBridge
 * that enables cross-field kindling through portal engrams.
 */
export class SelfModelField {
  private field: MnemicField
  private logger: ILogger

  constructor(logger: ILogger, dbPath?: string) {
    this.logger = logger.child ? logger.child('self-model') : logger
    const resolvedPath = dbPath ?? path.join(getDataDir(), 'self-model.db')
    this.field = new MnemicField(this.logger, resolvedPath)
    this.logger.info('Self-Model Field initialized', { dbPath: resolvedPath })
  }

  /**
   * Store any self-model engram. This is the primary storage API.
   *
   * Content is prefixed with `[type:name]` for FTS5 discoverability.
   * Tags are auto-generated from the engram type, metadata, and any extras.
   */
  store(
    nodeType: EngramType,
    name: string,
    description: string,
    metadata: Record<string, unknown>,
    options?: { embedding?: Float32Array | number[] | null; tags?: string[] },
  ): Engram {
    const extraTags = TAG_EXTRACTORS[nodeType]?.(metadata) ?? []

    return this.field.store({
      content: `${name} — ${description}`,
      nodeType,
      tags: ['self-model', nodeType, ...extraTags, ...(options?.tags ?? [])],
      provenance: 'self-model',
      metadata,
      embedding: options?.embedding ?? undefined,
    })
  }

  /**
   * Typed convenience for storing module engrams.
   */
  storeModule(name: string, description: string, metadata: ModuleMetadata, options?: StoreOptions): Engram {
    return this.store('module', name, description, metadata as unknown as Record<string, unknown>, options)
  }

  /**
   * Typed convenience for storing capability engrams.
   */
  storeCapability(name: string, description: string, metadata: CapabilityMetadata, options?: StoreOptions): Engram {
    return this.store('capability', name, description, metadata as unknown as Record<string, unknown>, options)
  }

  /**
   * Typed convenience for storing pattern engrams.
   */
  storePattern(name: string, description: string, metadata: PatternMetadata, options?: StoreOptions): Engram {
    return this.store('pattern', name, description, metadata as unknown as Record<string, unknown>, options)
  }

  /**
   * Typed convenience for storing principle engrams.
   */
  storePrinciple(name: string, description: string, options?: StoreOptions): Engram {
    return this.store('principle', name, description, {}, options)
  }

  /**
   * Typed convenience for storing weakness engrams.
   */
  storeWeakness(name: string, description: string, metadata: WeaknessMetadata, options?: StoreOptions): Engram {
    return this.store('weakness', name, description, metadata as unknown as Record<string, unknown>, options)
  }

  /**
   * Typed convenience for storing evolution engrams.
   */
  storeEvolution(name: string, description: string, metadata: EvolutionMetadata, options?: StoreOptions): Engram {
    return this.store('evolution', name, description, metadata as unknown as Record<string, unknown>, options)
  }

  /**
   * Create a portal engram — a bridge connection point to another field.
   * The InterFieldBridge calls this; callers generally don't need to.
   */
  createPortal(concept: string, linkedPortalId: string, fieldId: 'episodic' | 'self-model'): Engram {
    const metadata: PortalMetadata = {
      fieldId,
      linkedPortalId,
      bridgeConcept: concept,
      dampening: 0.4,
    }

    return this.field.store({
      content: `[portal:${concept}] Bridge to ${fieldId === 'self-model' ? 'episodic' : 'self-model'} field`,
      nodeType: 'portal',
      tags: ['portal', concept],
      provenance: 'inter-field-bridge',
      metadata: metadata as unknown as Record<string, unknown>,
    })
  }

  /**
   * Connect two engrams with an architectural relationship.
   */
  connect(sourceId: string, targetId: string, edgeType: SynapseType, weight?: number): MnemicSynapse {
    return this.field.connect({ sourceId, targetId, edgeType, weight })
  }

  get(id: string): Engram | null {
    return this.field.get(id)
  }

  update(id: string, patch: EngramUpdate): Engram | null {
    return this.field.update(id, patch)
  }

  delete(id: string): boolean {
    return this.field.delete(id)
  }

  /**
   * Retrieve from the self-model using kindling with SMF-tuned defaults.
   *
   * Multi-word queries use OR semantics (via FTS5 OR operator) because
   * architectural queries are conceptual — "spawn decisions" should find
   * modules mentioning either "spawn" or "decisions", not require both.
   */
  retrieve(query: string, options?: KindlingOptions & { limit?: number }): MnemicRetrievalHit[] {
    const orQuery = this.toOrQuery(query)
    return this.field.retrieve(orQuery, {
      ...SELF_MODEL_KINDLING_DEFAULTS,
      ...options,
    })
  }

  /**
   * List engrams by type with configurable limit.
   */
  list(nodeType?: EngramType, limit = 100): Engram[] {
    return this.field.list(limit, nodeType)
  }

  /**
   * Find module engrams by domain.
   */
  findModulesByDomain(domain: string, limit = 50): Engram[] {
    return this.field.searchText(domain, limit)
      .map(r => r.engram)
      .filter(e => e.nodeType === 'module')
  }

  /**
   * Find weaknesses, optionally filtered by severity.
   */
  findWeaknesses(severity?: WeaknessMetadata['severity'], limit = 100): Engram[] {
    const engrams = this.field.list(limit, 'weakness')
    if (!severity) return engrams
    return engrams.filter(e => {
      const meta = e.metadata as unknown as WeaknessMetadata
      return meta.severity === severity
    })
  }

  /**
   * Get evolution history for a module path.
   */
  getEvolutionHistory(modulePath: string, limit = 50): Engram[] {
    return this.field.searchText(modulePath, limit)
      .map(r => r.engram)
      .filter(e => e.nodeType === 'evolution')
      .sort((a, b) => b.t - a.t)
  }

  /**
   * Get all modules and their dependency relationships.
   */
  getDependencyGraph(): Array<{ module: Engram; dependsOn: Engram[] }> {
    const modules = this.field.list(500, 'module')
    return modules.map(mod => {
      const { engrams, synapses } = this.field.neighbors(mod.id)
      const dependsOn = synapses
        .filter(s => s.edgeType === 'depends_on' && s.sourceId === mod.id)
        .map(s => engrams.find(e => e.id === s.targetId))
        .filter((e): e is Engram => e !== undefined)
      return { module: mod, dependsOn }
    })
  }

  stats(): FieldStats & { selfModelTypes: Record<string, number> } {
    const base = this.field.stats()
    const typeCounts: Record<string, number> = {}
    for (const nodeType of SELF_MODEL_ENGRAM_TYPES) {
      const count = this.field.list(1, nodeType).length
      if (count > 0) typeCounts[nodeType] = this.field.list(10000, nodeType).length
    }
    return { ...base, selfModelTypes: typeCounts }
  }

  async consolidate(): Promise<void> {
    await this.field.consolidate()
    this.logger.debug('Self-Model Field consolidated')
  }

  getField(): MnemicField {
    return this.field
  }

  /**
   * Transform a multi-word query into FTS5 OR syntax.
   * "spawn decisions" → "spawn OR decisions"
   *
   * Single words and queries that already contain FTS5 operators pass through.
   * This gives the self-model broad conceptual matching rather than requiring
   * every term to appear in the same engram.
   */
  private toOrQuery(query: string): string {
    const trimmed = query.trim()
    if (!trimmed) return trimmed
    if (/\b(OR|AND|NOT|NEAR)\b/.test(trimmed)) return trimmed
    if (trimmed.includes('"')) return trimmed

    const words = trimmed.split(/\s+/).filter(w => w.length > 0)
    if (words.length <= 1) return trimmed

    return words.join(' OR ')
  }

  close(): void {
    this.field.close()
    this.logger.info('Self-Model Field closed')
  }
}

interface StoreOptions {
  embedding?: Float32Array | number[] | null
  tags?: string[]
}
