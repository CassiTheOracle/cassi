import path from 'node:path'
import type { ILogger } from '@cassicore/foundation'
import { getDataDir } from '@cassicore/foundation'
import { MnemicField } from '../index.js'
import type {
  Engram, EngramUpdate, MnemicRetrievalHit, KindlingOptions,
  SynapseType,
} from '../types.js'
import type {
  PaperMetadata, TechniqueMetadata, FindingMetadata, SurveyMetadata,
  AlgorithmMetadata, BenchmarkMetadata, TechniqueComparison,
  KnowledgeSemanticType,
} from './types.js'
import {
  KNOWLEDGE_SEMANTIC_TYPES, KNOWLEDGE_KINDLING_DEFAULTS,
  KNOWLEDGE_SYNAPSE_PROPAGATION, semanticToEngramType, semanticToSynapseType,
} from './types.js'
import type {
  ModelKnowledgeProvider, ModelEntity, ModelEdge, ModelPath,
} from '@cassicore/aurora'

const TAG_EXTRACTORS: Record<string, (meta: Record<string, unknown>) => string[]> = {
  paper: (m) => [
    ...(m.authors as string[] ?? []),
    String(m.year ?? ''),
    (m.venue as string) ?? '',
  ].filter(Boolean),
  technique: (m) => [(m.domain as string) ?? ''].filter(Boolean),
  finding: (m) => [(m.evidenceType as string) ?? ''].filter(Boolean),
  survey: () => [],
  algorithm: (m) => [(m.category as string) ?? ''].filter(Boolean),
  benchmark: () => [],
  dataset: () => [],
  model: () => [],
}

/**
 * KnowledgeField — a third Mnemic Field for external research and technique knowledge.
 *
 * Unlike the episodic field (what happened) and self-model (what things ARE),
 * the KnowledgeField stores what the world knows (papers, techniques, findings).
 *
 * It implements ModelKnowledgeProvider so Aurora's Claustrum can seed from it
 * directly — research knowledge becomes part of the model's mental state.
 *
 * All engrams are shared: "hot" engrams (high potentiation) naturally surface
 * in mental state; "cold" engrams remain available via explicit MCP tool calls.
 */
export class KnowledgeField implements ModelKnowledgeProvider {
  private field: MnemicField
  private logger: ILogger

  constructor(logger: ILogger, dbPath?: string) {
    this.logger = logger.child ? logger.child('knowledge-field') : logger
    const resolvedPath = dbPath ?? path.join(getDataDir(), 'knowledge-field.db')
    this.field = new MnemicField(this.logger, resolvedPath)
    this.logger.info('Knowledge Field initialized', { dbPath: resolvedPath })
  }

  // contributing:ignore — Typed Storage

  private storeKnowledge(
    semanticType: KnowledgeSemanticType,
    name: string,
    description: string,
    metadata: Record<string, unknown>,
    options?: { embedding?: Float32Array | number[] | null; tags?: string[] },
  ): Engram {
    const extraTags = TAG_EXTRACTORS[semanticType]?.(metadata) ?? []
    const engramType = semanticToEngramType(semanticType)
    return this.field.store({
      content: `${name} — ${description}`,
      nodeType: engramType,
      tags: ['knowledge', semanticType, ...extraTags, ...(options?.tags ?? [])],
      provenance: 'knowledge-field',
      metadata: { ...metadata, knowledgeType: semanticType },
      embedding: options?.embedding ?? undefined,
    })
  }

  storePaper(title: string, abstract: string, metadata: PaperMetadata, options?: StoreOptions): Engram {
    return this.storeKnowledge('paper', title, abstract, metadata as unknown as Record<string, unknown>, options)
  }

  storeTechnique(name: string, description: string, metadata: TechniqueMetadata, options?: StoreOptions): Engram {
    return this.storeKnowledge('technique', name, description, metadata as unknown as Record<string, unknown>, options)
  }

  storeFinding(claim: string, evidence: string, metadata: FindingMetadata, options?: StoreOptions): Engram {
    return this.storeKnowledge('finding', claim, evidence, metadata as unknown as Record<string, unknown>, options)
  }

  storeSurvey(topic: string, summary: string, metadata: SurveyMetadata, options?: StoreOptions): Engram {
    return this.storeKnowledge('survey', topic, summary, metadata as unknown as Record<string, unknown>, options)
  }

  storeAlgorithm(name: string, description: string, metadata: AlgorithmMetadata, options?: StoreOptions): Engram {
    return this.storeKnowledge('algorithm', name, description, metadata as unknown as Record<string, unknown>, options)
  }

  storeBenchmark(name: string, description: string, metadata: BenchmarkMetadata, options?: StoreOptions): Engram {
    return this.storeKnowledge('benchmark', name, description, metadata as unknown as Record<string, unknown>, options)
  }

  // contributing:ignore — Retrieval

  /**
   * Retrieve from knowledge using kindling with precision-tuned defaults.
   */
  async retrieve(query: string, options?: KindlingOptions & { limit?: number }): Promise<MnemicRetrievalHit[]> {
    return this.field.retrieve(query, {
      ...KNOWLEDGE_KINDLING_DEFAULTS,
      ...options,
    })
  }

  /**
   * Direct kindling — returns the full LuminalSet for advanced consumers.
   */
  kindle(query: string, options?: KindlingOptions) {
    return this.field.kindle(null, query, {
      ...KNOWLEDGE_KINDLING_DEFAULTS,
      ...options,
    })
  }

  // contributing:ignore — ModelKnowledgeProvider (for Aurora/Claustrum)

  describe(entity: string): ModelEntity | null {
    const hits = this.field.searchText(entity, 5)
    if (hits.length === 0) return null

    const relations: Array<{ relation: string; target: string; confidence: number; layerMin: number; layerMax: number }> = []

    for (const hit of hits.slice(0, 3)) {
      const neighbors = this.field.neighbors(hit.engram.id)
      for (const syn of neighbors.synapses) {
        const targetEngram = neighbors.engrams.find(e => e.id === (syn.sourceId === hit.engram.id ? syn.targetId : syn.sourceId))
        if (!targetEngram) continue
        const propWeight = KNOWLEDGE_SYNAPSE_PROPAGATION[syn.edgeType as keyof typeof KNOWLEDGE_SYNAPSE_PROPAGATION] ?? 0.5
        relations.push({
          relation: syn.edgeType,
          target: targetEngram.content.slice(0, 80),
          confidence: syn.weight * propWeight * hit.score,
          layerMin: 14,
          layerMax: 27,
        })
      }
    }

    relations.sort((a, b) => b.confidence - a.confidence)

    return {
      name: entity,
      relations: relations.slice(0, 20),
      totalRelations: relations.length,
    }
  }

  subgraph(entity: string, radius: number = 1): ModelEdge[] {
    const edges: ModelEdge[] = []
    const visited = new Set<string>()
    const queue: Array<{ entity: string; depth: number }> = [{ entity, depth: 0 }]

    while (queue.length > 0) {
      const current = queue.shift()!
      if (visited.has(current.entity)) continue
      visited.add(current.entity)

      const hits = this.field.searchText(current.entity, 3)
      if (hits.length === 0) continue

      for (const hit of hits) {
        const neighbors = this.field.neighbors(hit.engram.id)
        for (const syn of neighbors.synapses) {
          const otherId = syn.sourceId === hit.engram.id ? syn.targetId : syn.sourceId
          const other = neighbors.engrams.find(e => e.id === otherId)
          if (!other) continue

          edges.push({
            subject: hit.engram.content.slice(0, 60),
            relation: syn.edgeType,
            object: other.content.slice(0, 60),
            confidence: syn.weight,
            layerMin: 14,
            layerMax: 27,
          })

          if (current.depth < radius) {
            queue.push({ entity: other.content.slice(0, 60), depth: current.depth + 1 })
          }
        }
      }

      if (edges.length > 200) break
    }

    return edges
  }

  shortestPath(_from: string, _to: string): ModelPath | null {
    return null // contributing:ignore — TODO: implement if needed
  }

  exists(entity: string): boolean {
    return this.field.searchText(entity, 1).length > 0
  }

  search(query: string, limit: number = 5): ModelEntity[] {
    const hits = this.field.searchText(query, limit)
    return hits.map(hit => ({
      name: hit.engram.content.slice(0, 80),
      relations: [],
      totalRelations: 0,
    }))
  }

  // contributing:ignore — Specific Lookups

  private hasKnowledgeType(engram: Engram, type: KnowledgeSemanticType): boolean {
    return (engram.metadata as { knowledgeType?: string } | null | undefined)?.knowledgeType === type
  }

  listByKnowledgeType(type: KnowledgeSemanticType, limit = 100): Engram[] {
    return this.field.list(10000)
      .filter(e => this.hasKnowledgeType(e, type))
      .slice(0, limit)
  }

  findTechniquesByDomain(domain: string, limit = 50): Engram[] {
    return this.field.searchText(domain, limit * 2)
      .map(r => r.engram)
      .filter(e => this.hasKnowledgeType(e, 'technique'))
      .slice(0, limit)
  }

  findPapersByAuthor(author: string, limit = 50): Engram[] {
    return this.field.searchText(author, limit * 2)
      .map(r => r.engram)
      .filter(e => this.hasKnowledgeType(e, 'paper'))
      .slice(0, limit)
  }

  findPaperByTitle(title: string): Engram | null {
    return this.field.searchText(title, 20)
      .map(r => r.engram)
      .find(e => this.hasKnowledgeType(e, 'paper') && e.content.startsWith(title)) ?? null
  }

  findRelatedTechniques(techniqueId: string): Engram[] {
    const { engrams } = this.field.neighbors(techniqueId)
    return engrams.filter(e => this.hasKnowledgeType(e, 'technique'))
  }

  getDeepDive(id: string): {
    engram: Engram
    neighbors: Engram[]
    synapses: ReturnType<MnemicField['neighbors']>['synapses']
  } | null {
    const engram = this.field.get(id)
    if (!engram) return null
    const { engrams, synapses } = this.field.neighbors(id)
    return { engram, neighbors: engrams, synapses }
  }

  compareTechniques(idA: string, idB: string): TechniqueComparison | null {
    const a = this.field.get(idA)
    const b = this.field.get(idB)
    if (!a || !b) return null

    const metaA = a.metadata as unknown as TechniqueMetadata
    const metaB = b.metadata as unknown as TechniqueMetadata

    const sharedDomains = [metaA.domain, metaB.domain].filter((d, i, arr) => d && arr.indexOf(d) === i)

    const contradictions: Array<{ claimA: string; claimB: string }> = []
    const { synapses } = this.field.neighbors(idA)
    for (const syn of synapses) {
      if (syn.edgeType === 'contradicts' && (syn.targetId === idB || syn.sourceId === idB)) {
        contradictions.push({ claimA: a.content, claimB: b.content })
      }
    }

    const benchA = metaA.benchmarks ?? []
    const benchB = metaB.benchmarks ?? []
    const benchmarkDelta: TechniqueComparison['benchmarkDelta'] = []

    for (const ba of benchA) {
      const bb = benchB.find(b => b.dataset === ba.dataset && b.metric === ba.metric)
      if (bb) {
        benchmarkDelta.push({
          dataset: ba.dataset,
          metric: ba.metric,
          scoreA: ba.score,
          scoreB: bb.score,
          delta: ba.score - bb.score,
        })
      }
    }

    return {
      techniqueA: { id: idA, name: a.content.split(' — ')[0], content: a.content, metadata: metaA },
      techniqueB: { id: idB, name: b.content.split(' — ')[0], content: b.content, metadata: metaB },
      sharedDomains,
      contradictions,
      benchmarkDelta,
    }
  }

  // contributing:ignore — Bridge / Passthrough

  get(id: string): Engram | null {
    return this.field.get(id)
  }

  update(id: string, patch: EngramUpdate): Engram | null {
    return this.field.update(id, patch)
  }

  delete(id: string): boolean {
    return this.field.delete(id)
  }

  connect(sourceId: string, targetId: string, edgeType: SynapseType, weight?: number) {
    return this.field.connect({ sourceId, targetId, edgeType, weight })
  }

  list(nodeType?: string, limit = 100): Engram[] {
    return this.field.list(limit, nodeType)
  }

  getField(): MnemicField {
    return this.field
  }

  stats() {
    const base = this.field.stats()
    const typeCounts: Record<string, number> = {}
    for (const semanticType of KNOWLEDGE_SEMANTIC_TYPES) {
      const count = this.listByKnowledgeType(semanticType, 10000).length
      if (count > 0) typeCounts[semanticType] = count
    }
    return { ...base, knowledgeTypes: typeCounts }
  }

  async backfillEmbeddings(limit = 1000) {
    const result = await this.field.backfillEmbeddings(limit)
    this.logger.info('Knowledge Field backfilled embeddings', result)
    return result
  }

  async consolidate() {
    await this.field.consolidate()
    this.logger.debug('Knowledge Field consolidated')
  }

  close(): void {
    this.field.close()
    this.logger.info('Knowledge Field closed')
  }
}

interface StoreOptions {
  embedding?: Float32Array | number[] | null
  tags?: string[]
}
