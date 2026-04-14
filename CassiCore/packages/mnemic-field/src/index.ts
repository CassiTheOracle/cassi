import Database from 'better-sqlite3'
import fs from 'node:fs'
import path from 'node:path'
import type { ILogger } from '../../../types/interfaces.js'
import { getEmbeddingService } from '../embeddings/embedding-service.js'
import { getDataDir } from '../../utils/paths.js'
import { Cortex, computeSpikeImportance, computeAlpha } from './cortex.js'
import { FilamentCortex } from './filament-cortex.js'
import { KindlingEngine } from './kindling.js'
import { ConsolidationEngine } from './consolidation.js'
import { GradientEngine } from './backpropagation.js'
import { MigrationJobStore, type MigrationJobRecord, type MigrationJobSpec } from './migration-jobs.js'
import { migrateChunk, migrateMemoryAndArchives, migrateMemoryOnly } from './migrate-memory.js'
import type { ConsolidationResult, ConsolidationOptions } from './consolidation.js'
import { projectTo2D, projectTo2DAsync, projectTo2DFromSAB, projectSingle, buildProjectionState, type ProjectionState } from './umap.js'
import { segmentEngram } from './segmentation.js'
import { EntityLinker } from './filament-entities.js'
import { FilamentConsolidator } from './filament-consolidation.js'
import { attune, AffectRegister, affectSimilarity } from './affect.js'
import type { AffectState } from './types.js'
import type { CorticalField } from '../cortex/index.js'
import { extractChains, scoreCrystallization, computeExpertiseMetrics, propagateStaleness } from './filament-chains.js'
import { renderWithZoom } from './filament-renderer.js'
import type { IProvider } from '../../../types/runtime.js'
import { FilamentAnalyzer } from './filament-llm.js'
import type {
  Engram, EngramCreate, EngramUpdate,
  MnemicSynapse, SynapseCreate,
  ActivationSpike, SpikeCreate,
  Nucleus, NucleusCreate,
  SpatialQuery, EngramSearchResult, TensionPair, TensionReport, FieldStats, MnemicRetrievalHit,
  TaskComplexity, LuminalSet, KindlingOptions, SpikeOutcome,
  Filament, FilamentAnnotation, EngramPosition,
  FilamentChain, CrystallizationScore, ExpertiseMetrics, DelegationContext,
  ZoomEntry, RenderOptions,
  NeuralKindlingConfig,
  BackpropConfig,
} from './types.js'
import { SPARK_POINT_DEFAULTS, POTENTIATION_DEFAULTS } from './types.js'

const REPROJECTION = {
  cooldownMs: 30 * 60 * 1000,    // 30 min between runs
  maxFailures: 2,                 // block after this many consecutive failures
} as const

export { Cortex } from './cortex.js'
export { FilamentCortex } from './filament-cortex.js'
export { KindlingEngine } from './kindling.js'
export { ConsolidationEngine } from './consolidation.js'
export { GradientEngine } from './backpropagation.js'
export { CodeStore } from './code-store.js'
export { CodeIngestor } from './code-ingestor.js'
export { GitNexusBridge } from './gitnexus-bridge.js'
export { SelfModelField, InterFieldBridge, SelfModelIngestor } from './self-model/index.js'
export type {
  ModuleMetadata, CapabilityMetadata, PatternMetadata,
  WeaknessMetadata, EvolutionMetadata, PortalMetadata,
  BridgeConfig, CrossFieldRetrievalHit, CrossFieldResult,
} from './self-model/index.js'
export type {
  IngestResult as SelfModelIngestResult,
  IngestOptions as SelfModelIngestOptions,
} from './self-model/index.js'
export {
  SELF_MODEL_ENGRAM_TYPES, SELF_MODEL_SYNAPSE_TYPES,
  SELF_MODEL_KINDLING_DEFAULTS, BRIDGE_DEFAULTS,
} from './self-model/index.js'
export { segmentEngram } from './segmentation.js'
export { EntityLinker, extractEntities } from './filament-entities.js'
export { FilamentConsolidator } from './filament-consolidation.js'
export { FilamentAnalyzer } from './filament-llm.js'
export { extractChains, scoreCrystallization, computeExpertiseMetrics, propagateStaleness } from './filament-chains.js'
export { renderWithZoom } from './filament-renderer.js'
export type { FilamentSpan } from './segmentation.js'
export type { IngestOptions, IngestResult } from './code-ingestor.js'
export type { ConsolidationResult, ConsolidationOptions } from './consolidation.js'
export { projectTo2D, projectTo2DAsync, projectTo2DFromSAB, projectSingle, buildProjectionState } from './umap.js'
export type { ProjectionResult, ProjectionState, UMAPOptions, UMAPProgressEvent } from './umap.js'
export type {
  Engram, EngramCreate, EngramUpdate,
  MnemicSynapse, SynapseCreate,
  ActivationSpike, SpikeCreate,
  Nucleus, NucleusCreate,
  SpatialQuery, EngramSearchResult, TensionPair, TensionReport, FieldStats, MnemicRetrievalHit,
  TaskComplexity, LuminalSet, KindlingOptions, ChargedEngram,
  Changeset, ChangesetCreate, ChangesetFile, ChangesetStatus, ChangesetFileOperation,
  SourceFileMetadata,
  Filament, FilamentCreate, FilamentSynapse, FilamentSynapseCreate,
  FilamentEntity, FilamentAnnotation, FilamentSynapseType, SegmentationConfig,
  FilamentChain, CrystallizationScore, ExpertiseMetrics, DelegationContext,
  ZoomEntry, ZoomLevel, RenderOptions, Tier3Config,
  Affect, AffectState, AffectLabel, AffectConfig,
  NeuralKindlingConfig, ForwardTrace, ForwardRecord, GradientRequest,
  BackpropConfig, BackpropResult, TraceGradientResult, SynapseOptimizerState,
} from './types.js'
export {
  ENGRAM_TYPES, SYNAPSE_TYPES, SYNAPSE_PROPAGATION,
  POTENTIATION_DEFAULTS, SPARK_POINT_DEFAULTS, KINDLING_DEFAULTS,
  FILAMENT_SYNAPSE_TYPES, FILAMENT_SYNAPSE_PROPAGATION,
  RENDER_DEFAULTS, TIER3_DEFAULTS, CHAIN_EDGE_TYPES,
  SEGMENTATION_DEFAULTS, FILAMENT_KINDLING_DEFAULTS,
  AFFECT_DEFAULTS, BACKPROP_DEFAULTS,
} from './types.js'
export { attune, AffectRegister, resolveLabel, affectSimilarity, emotionalIntensity } from './affect.js'

export class MnemicField {
  private cortex: Cortex
  private filamentCortex: FilamentCortex
  private entityLinker: EntityLinker
  private kindlingEngine: KindlingEngine
  private consolidationEngine: ConsolidationEngine
  private gradientEngine: GradientEngine
  private migrationJobs: MigrationJobStore
  private logger: ILogger
  private projectionState: ProjectionState | null = null
  private reprojectionInFlight: Promise<number> | null = null
  private reprojectionFailures = 0
  private lastReprojectionAt = 0
  private filamentAnalyzer: FilamentAnalyzer | null = null
  private affectRegister: AffectRegister
  private corticalField?: CorticalField
  private db: Database.Database  // Store for persistence operations

  constructor(logger: ILogger, dbOrPath?: Database.Database | string) {
    this.logger = logger.child ? logger.child('mnemic-field') : logger

    let db: Database.Database
    if (typeof dbOrPath === 'string' || dbOrPath === undefined) {
      const dbPath = dbOrPath ?? path.join(getDataDir(), 'mnemic-field.db')
      const dir = path.dirname(dbPath)
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
      db = new Database(dbPath)
      db.pragma('journal_mode = WAL')
      db.pragma('busy_timeout = 5000')
      db.pragma('foreign_keys = ON')
    } else {
      db = dbOrPath
    }

    this.db = db  // Store for persistence
    this.cortex = new Cortex(db, logger)
    this.filamentCortex = new FilamentCortex(db, logger)
    this.entityLinker = new EntityLinker(this.filamentCortex, logger)
    this.kindlingEngine = new KindlingEngine(this.cortex, logger, this.filamentCortex)
    const filamentConsolidator = new FilamentConsolidator(this.filamentCortex, this.cortex, logger)
    this.gradientEngine = new GradientEngine(this.cortex, logger)
    this.consolidationEngine = new ConsolidationEngine(this.cortex, logger, filamentConsolidator, this.gradientEngine)
    this.migrationJobs = new MigrationJobStore(db)
    this.affectRegister = new AffectRegister()

    // Initialize projection state from existing positions in DB (if available)
    this.projectionState = this._restoreProjectionState()

    this.logger.info('Mnemic Field initialized', {
      projectionStateRestored: this.projectionState !== null,
      validPositions: this.cortex.countValidPositions(),
    })
  }

  /**
   * Restore projection state from database if valid positions exist.
   * This avoids triggering expensive full reprojection on startup.
   */
  private _restoreProjectionState(): ProjectionState | null {
    // Check if we have enough positions to build a useful state
    const validPositions = this.cortex.countValidPositions()
    if (validPositions < 100) {
      this.logger.debug('Not enough valid positions to restore projection state', { count: validPositions })
      return null
    }

    // Try to load from persisted state first
    const persisted = this._loadPersistedProjectionState()
    if (persisted) {
      this.logger.info('Restored projection state from persisted cache', {
        vectorCount: persisted.referenceEmbeddings.length,
      })
      return persisted
    }

    // Fall back to rebuilding from current DB positions
    this.logger.info('Rebuilding projection state from DB positions', { validPositions })
    return this.rebuildProjection()
  }

  /**
   * Persist projection state to mnemic_meta table for fast restoration.
   * Stores reference embeddings and positions as JSON.
   */
  private _saveProjectionState(state: ProjectionState): void {
    try {
      // Serialize state: embeddings as nested arrays, positions as {x, y} objects
      const serialized = JSON.stringify({
        referenceEmbeddings: state.referenceEmbeddings,
        referencePositions: state.referencePositions,
        nNeighbors: state.nNeighbors,
        version: 1,
        timestamp: Date.now(),
      })

      // Upsert to mnemic_meta
      this.db.prepare(`
        INSERT OR REPLACE INTO mnemic_meta (key, value)
        VALUES ('projection_state', ?)
      `).run(serialized)

      this.logger.debug('Projection state persisted', {
        vectorCount: state.referenceEmbeddings.length,
        sizeBytes: serialized.length,
      })
    } catch (err) {
      this.logger.warn('Failed to persist projection state', { error: String(err) })
    }
  }

  /**
   * Load persisted projection state from mnemic_meta table.
   */
  private _loadPersistedProjectionState(): ProjectionState | null {
    try {
      const row = this.db.prepare(
        `SELECT value FROM mnemic_meta WHERE key = 'projection_state'`
      ).get() as { value: string } | undefined

      if (!row) return null

      const parsed = JSON.parse(row.value) as {
        referenceEmbeddings: number[][]
        referencePositions: { x: number; y: number }[]
        nNeighbors: number
        version: number
        timestamp: number
      }

      // Validate the loaded state
      if (!parsed.referenceEmbeddings || parsed.referenceEmbeddings.length < 2) {
        return null
      }

      return {
        referenceEmbeddings: parsed.referenceEmbeddings,
        referencePositions: parsed.referencePositions,
        nNeighbors: parsed.nNeighbors,
      }
    } catch (err) {
      this.logger.warn('Failed to load persisted projection state', { error: String(err) })
      return null
    }
  }

  /**
   * Clear persisted projection state (e.g., before full reprojection).
   */
  private _clearPersistedProjectionState(): void {
    try {
      this.db.prepare(`DELETE FROM mnemic_meta WHERE key = 'projection_state'`).run()
    } catch (err) {
      this.logger.warn('Failed to clear persisted projection state', { error: String(err) })
    }
  }

  /**
   * Store a new engram. If embedding is provided but x/y are not,
   * projects into the existing field topology via nearest-neighbor placement.
   */
  store(input: EngramCreate): Engram {
    const shouldProject = input.embedding && input.x === undefined && input.y === undefined
    let x = input.x
    let y = input.y

    if (shouldProject && input.embedding) {
      const vec = input.embedding instanceof Float32Array
        ? Array.from(input.embedding)
        : input.embedding
      const pos = this.projectNewVector(vec)
      x = pos.x
      y = pos.y
    }

    const affect = attune(input.content)
    const metadata = { ...input.metadata, affect }

    const engram = this.cortex.createEngram({ ...input, x, y, metadata })

    const spans = segmentEngram(engram.content, engram.nodeType)
    if (spans.length > 0) {
      const filaments = this.filamentCortex.createFilamentsBatch(
        spans.map(s => ({
          engramId: engram.id,
          spanStart: s.spanStart,
          spanEnd: s.spanEnd,
          content: s.content,
        }))
      )
      this.entityLinker.linkFilaments(filaments)
    }

    return engram
  }

  get(id: string): Engram | null {
    return this.cortex.getEngram(id)
  }

  update(id: string, update: EngramUpdate): Engram | null {
    return this.cortex.updateEngram(id, update)
  }

  delete(id: string): boolean {
    return this.cortex.deleteEngram(id)
  }

  list(limit?: number, nodeType?: string): Engram[] {
    return this.cortex.listEngrams(limit, nodeType)
  }

  connect(input: SynapseCreate): MnemicSynapse {
    return this.cortex.createSynapse(input)
  }

  disconnect(sourceId: string, targetId: string, edgeType: string): boolean {
    return this.cortex.deleteSynapse(sourceId, targetId, edgeType)
  }

  neighbors(engramId: string): { engrams: Engram[]; synapses: MnemicSynapse[] } {
    const synapses = this.cortex.getNeighborSynapses(engramId)
    const engrams = this.cortex.getNeighborEngrams(engramId)
    return { engrams, synapses }
  }

  spike(input: SpikeCreate): ActivationSpike {
    return this.cortex.recordSpike(input)
  }

  spikes(engramId: string, limit?: number): ActivationSpike[] {
    return this.cortex.getSpikes(engramId, limit)
  }

  spikeCount(engramId: string): number {
    return this.cortex.getSpikeCount(engramId)
  }

  createNucleus(input: NucleusCreate): Nucleus {
    return this.cortex.createNucleus(input)
  }

  nuclei(): Nucleus[] {
    return this.cortex.listNuclei()
  }

  /**
   * Spatial range query using the R-tree index.
   */
  querySpatial(query: SpatialQuery): Engram[] {
    return this.cortex.spatialQuery(query)
  }

  getPositions(limit?: number): EngramPosition[] {
    return this.cortex.getPositions(limit)
  }

  /**
   * Full-text search over engram content, tags, provenance.
   */
  searchText(query: string, limit?: number): EngramSearchResult[] {
    return this.cortex.searchText(query, limit)
  }

  /**
   * Find contradicting engrams that both have high potentiation.
   */
  tensions(minPotentiation?: number, limit?: number): TensionPair[] {
    return this.cortex.getTensionPairs(minPotentiation, limit)
  }

  /**
   * Generate a tension report: all unresolved contradictions with recommendations.
   */
  tensionReport(minPotentiation = 0.3, limit = 10): TensionReport {
    const pairs = this.cortex.getTensionPairs(minPotentiation, limit)
    const totalTension = pairs.reduce((s, p) => s + p.tension, 0)
    const highestTension = pairs.length > 0 ? pairs[0].tension : 0

    let recommendation = 'No significant tensions detected.'
    if (pairs.length > 0) {
      const top = pairs[0]
      recommendation = `${pairs.length} tension(s) found. Highest: "${top.engramA.content.slice(0, 60)}" contradicts "${top.engramB.content.slice(0, 60)}" (tension: ${top.tension.toFixed(3)}). Consider creating a decision engram to resolve.`
    }

    return { pairs, totalTension, highestTension, recommendation }
  }

  computeSpikeImportance(engramId: string): number {
    return computeSpikeImportance(this.cortex.getSpikes(engramId, 200), POTENTIATION_DEFAULTS.decayRate)
  }

  computeAlpha(engramId: string): number {
    return computeAlpha(this.cortex.getSpikeCount(engramId), POTENTIATION_DEFAULTS)
  }

  /**
   * Compute effective spark point for an engram given task complexity.
   */
  effectiveSparkPoint(engramId: string, complexity: TaskComplexity = 'normal'): number {
    const engram = this.cortex.getEngram(engramId)
    if (!engram) return SPARK_POINT_DEFAULTS.baseThreshold

    const modifier = SPARK_POINT_DEFAULTS.taskModifiers[complexity]
    const base = SPARK_POINT_DEFAULTS.baseThreshold * modifier
    const reduction = engram.potentiation * SPARK_POINT_DEFAULTS.potentiationScale

    return Math.max(0.01, base - reduction)
  }

  stats(): FieldStats {
    const base = this.cortex.stats()
    const fStats = this.filamentCortex.stats()
    return {
      ...base,
      filamentCount: fStats.filamentCount,
      filamentSynapseCount: fStats.filamentSynapseCount,
      filamentEntityCount: fStats.entityCount,
    }
  }

  /**
   * Primary retrieval API for runtime consumers.
   * Uses kindling first, falls back to text search when needed.
   */
  retrieve(
    query: string,
    options?: KindlingOptions & { limit?: number },
  ): MnemicRetrievalHit[] {
    const limit = options?.limit ?? options?.maxLuminalSize ?? 8
    const luminal = this.kindle(null, query, {
      ...options,
      maxLuminalSize: limit,
      includeText: true,
      currentAffect: options?.currentAffect ?? this.affectRegister.getAffect(),
    })

    if (luminal.engrams.length > 0) {
      const excerptMap = new Map<string, { content: string; similarity: number }>()
      if (luminal.filamentAnnotations) {
        for (const ann of luminal.filamentAnnotations) {
          const existing = excerptMap.get(ann.engramId)
          if (!existing || ann.similarity > existing.similarity) {
            excerptMap.set(ann.engramId, { content: ann.content, similarity: ann.similarity })
          }
        }
      }

      return luminal.engrams.map(hit => ({
        id: hit.engram.id,
        content: hit.engram.content,
        nodeType: hit.engram.nodeType,
        score: hit.charge,
        charge: hit.charge,
        potentiation: hit.engram.potentiation,
        provenance: hit.engram.provenance,
        tags: hit.engram.tags,
        metadata: hit.engram.metadata,
        filamentExcerpt: excerptMap.get(hit.engram.id)?.content,
      }))
    }

    return this.searchText(query, limit).map(r => ({
      id: r.engram.id,
      content: r.engram.content,
      nodeType: r.engram.nodeType,
      score: r.score,
      charge: 0,
      potentiation: r.engram.potentiation,
      provenance: r.engram.provenance,
      tags: r.engram.tags,
      metadata: r.engram.metadata,
    }))
  }

  createMigrationJob(spec: MigrationJobSpec): MigrationJobRecord {
    return this.migrationJobs.create(spec)
  }

  getMigrationJob(id: string): MigrationJobRecord | null {
    return this.migrationJobs.get(id)
  }

  listMigrationJobs(limit = 20): MigrationJobRecord[] {
    return this.migrationJobs.list(limit)
  }

  updateMigrationJob(id: string, patch: Partial<MigrationJobRecord>): MigrationJobRecord | null {
    return this.migrationJobs.updateProgress(id, patch)
  }

  async runMigrationJob(
    id: string,
    runner: Pick<typeof import('../embeddings/embedding-service.js'), never> | null,
    options?: { logger?: ILogger; embeddingProvider?: (text: string) => Promise<number[] | null> },
  ): Promise<MigrationJobRecord> {
    const job = this.getMigrationJob(id)
    if (!job) throw new Error(`Unknown migration job: ${id}`)

    const existing = this.getMigrationJob(id)
    if (!existing) throw new Error(`Unknown migration job: ${id}`)
    if (existing.status === 'running') return existing

    this.updateMigrationJob(id, { status: 'running', errorText: null })

    try {
      const current = this.getMigrationJob(id)
      if (!current) throw new Error(`Unknown migration job: ${id}`)

      const result = await migrateChunk(this.logger, {
        sourceDbPath: current.sourceDbPath,
        targetField: this,
        includeArchived: current.includeArchived,
        migrateArchives: current.migrateArchives,
        inferSynapses: current.inferSynapses,
        limit: current.memoryLimit,
        archiveLimit: current.archiveLimit,
        archiveLinkLimit: current.archiveLinkLimit,
        microChunkTokenTarget: current.microChunkTokenTarget,
        enableMicroChunking: current.enableMicroChunking,
        embeddingProvider: options?.embeddingProvider,
        memoryOffset: current.nextMemoryOffset,
        archiveOffset: current.nextArchiveOffset,
        linkOffset: current.nextLinkOffset,
        memoryBatchSize: Math.min(current.memoryLimit ?? 250, 250),
        archiveBatchSize: Math.min(current.archiveLimit ?? 200, 200),
        linkBatchSize: Math.min(current.archiveLinkLimit ?? 1000, 1000),
        phase: current.phase,
      })

      const updated = this.updateMigrationJob(id, {
        status: result.done ? 'completed' : 'paused',
        phase: result.phase,
        migratedMemories: current.migratedMemories + result.migrated,
        migratedArchives: current.migratedArchives + result.archivedMigrated,
        createdSynapses: current.createdSynapses + result.synapsesCreated,
        createdFragments: current.createdFragments + result.fragmentEngramsCreated,
        nextMemoryOffset: result.nextMemoryOffset,
        nextArchiveOffset: result.nextArchiveOffset,
        nextLinkOffset: result.nextLinkOffset,
        completedAt: result.done ? new Date().toISOString() : null,
      })
      if (!updated) throw new Error(`Failed to update migration job: ${id}`)
      return updated
    } catch (err) {
      const updated = this.updateMigrationJob(id, {
        status: 'failed',
        errorText: String(err),
      })
      if (!updated) throw err
      return updated
    }
  }


  listNuclei(): Nucleus[] {
    return this.cortex.listNuclei()
  }

  listAbstractions(limit = 50): Engram[] {
    return this.cortex.listEngrams(limit, 'abstraction')
  }

  /**
   * Rebuild projection state from current engram embeddings and positions.
   * The state caches reference data for fast online projection of new engrams.
   * Call after bulk imports or periodically during consolidation.
   * Also persists the state to DB for restoration on next startup.
   */
  rebuildProjection(): ProjectionState | null {
    const embData = this.cortex.getEmbeddingVectorsWithPositions(10000)

    if (embData.length < 2) {
      this.projectionState = null
      this._clearPersistedProjectionState()
      return null
    }

    const vectors = embData.map(e => Array.from(e.embedding))
    const positions = embData.map(e => ({ x: e.x, y: e.y }))
    this.projectionState = buildProjectionState(vectors, positions)
    this.logger.debug('Projection state rebuilt', { vectorCount: vectors.length })

    // Persist for fast restoration on next startup
    if (this.projectionState) {
      this._saveProjectionState(this.projectionState)
    }

    return this.projectionState
  }

  /**
   * Project a new vector into XY space using cached projection state.
   * If no state exists, rebuilds from current engrams.
   */
  private projectNewVector(vector: number[]): { x: number; y: number } {
    if (!this.projectionState) {
      this.rebuildProjection()
    }

    if (this.projectionState) {
      return projectSingle(vector, this.projectionState)
    }

    return { x: 0, y: 0 }
  }

  /**
   * Bulk reproject all engrams using UMAP on current embeddings.
   * Computes full non-linear projection preserving local neighborhoods.
   */
  reprojectAll(umapOptions?: import('./umap.js').UMAPOptions): number {
    const embData = this.cortex.getEmbeddingVectors(50000)

    if (embData.length < 2) return 0

    if (embData.length >= 50000) {
      this.logger.warn('reprojectAll (sync) capped at 50k embeddings — use reprojectAllAsync for full dataset')
    }

    const effectiveOptions = umapOptions ? { ...umapOptions } : {}
    if (embData.length > 10000 && !effectiveOptions.nEpochs) {
      effectiveOptions.nEpochs = Math.max(50, Math.floor(200 * 10000 / embData.length))
    }

    const vectors = embData.map(e => Array.from(e.embedding))
    const positions = projectTo2D(vectors, effectiveOptions)

    const updates = embData.map((e, i) => ({
      id: e.id,
      x: positions[i].x,
      y: positions[i].y,
    }))

    this.cortex.bulkUpdatePositions(updates)
    this.projectionState = buildProjectionState(vectors, positions)

    this.logger.info('Reprojected engrams via UMAP (sync)', { count: updates.length })
    return updates.length
  }

  /**
   * Async reprojection using a dedicated worker thread. Supports the full
   * dataset (no 50K cap) and uses NN-Descent for large datasets (>5K).
   * The daemon event loop stays responsive during the entire computation.
   */
  async reprojectAllAsync(umapOptions?: import('./umap.js').UMAPOptions): Promise<number> {
    // Prevent concurrent reprojections — each one allocates a multi-GB SAB
    if (this.reprojectionInFlight) {
      this.logger.info('Reprojection already in progress — waiting for it to finish')
      return this.reprojectionInFlight
    }

    // Block after repeated failures to avoid compounding memory pressure
    if (this.reprojectionFailures >= REPROJECTION.maxFailures) {
      this.logger.warn('Reprojection blocked — too many recent failures', {
        failures: this.reprojectionFailures,
      })
      return 0
    }

    // Cooldown: prevent excessive reprojection
    const now = Date.now()
    if (this.lastReprojectionAt > 0 && now - this.lastReprojectionAt < REPROJECTION.cooldownMs) {
      const elapsed = Math.round((now - this.lastReprojectionAt) / 1000)
      this.logger.info('Reprojection cooldown active — skipping', {
        elapsedSecs: elapsed,
        cooldownSecs: REPROJECTION.cooldownMs / 1000,
      })
      return 0
    }

    const promise = this._doReprojectAsync(umapOptions)
    this.reprojectionInFlight = promise
    try {
      return await promise
    } finally {
      this.reprojectionInFlight = null
    }
  }

  private async _doReprojectAsync(umapOptions?: import('./umap.js').UMAPOptions): Promise<number> {
    let { buffer, ids, dim, count } = this.cortex.packEmbeddingsIntoSAB()

    if (count < 2) return 0

    const effectiveOptions: import('./umap.js').ProjectTo2DFromSABOptions = umapOptions ? { ...umapOptions } : {}

    if (count > 10000 && !effectiveOptions.nEpochs) {
      effectiveOptions.nEpochs = Math.max(50, Math.floor(200 * 10000 / count))
    }

    effectiveOptions.onProgress = (event) => {
      this.logger.debug('UMAP worker progress', {
        phase: event.phase,
        progress: event.progress,
        ...(event.durationMs !== undefined ? { durationMs: event.durationMs } : {}),
        ...(event.updates !== undefined ? { updates: event.updates } : {}),
        ...(event.edgeCount !== undefined ? { edgeCount: event.edgeCount } : {}),
        ...(event.iter !== undefined ? { iter: event.iter } : {}),
      })
    }

    this.logger.info('Starting async reprojection via worker thread', {
      count,
      dim,
      epochs: effectiveOptions.nEpochs ?? 200,
      sabSizeMB: Math.round(buffer.byteLength / 1024 / 1024),
    })

    try {
      const { positions, stats } = await projectTo2DFromSAB(buffer, count, dim, effectiveOptions)

      const updates = ids.map((id, i) => ({
        id,
        x: positions[i].x,
        y: positions[i].y,
      }))

      this.cortex.bulkUpdatePositions(updates)

      // Build projection state from a sample — avoid loading all vectors again.
      const MAX_REF = 5000
      const packed = new Float32Array(buffer)
      const step = count > MAX_REF ? count / MAX_REF : 1
      const refEmb: number[][] = []
      const refPos: import('./umap.js').ProjectionResult[] = []
      for (let i = 0; i < Math.min(count, MAX_REF); i++) {
        const idx = Math.min(Math.floor(i * step), count - 1)
        const vec: number[] = new Array(dim)
        const off = idx * dim
        for (let d = 0; d < dim; d++) vec[d] = packed[off + d]
        refEmb.push(vec)
        refPos.push(positions[idx])
      }
      this.projectionState = buildProjectionState(refEmb, refPos)

      // Persist for fast restoration on next startup
      if (this.projectionState) {
        this._saveProjectionState(this.projectionState)
      }

      // Release large allocations so GC can reclaim them before we return
      buffer = null as any
      ids = null as any

      this.logger.info('Reprojected engrams via UMAP (async worker)', {
        count: updates.length,
        totalMs: stats.totalMs,
        knnMs: stats.knnMs,
        sgdMs: stats.sgdMs,
        edges: stats.edges,
      })

      this.lastReprojectionAt = Date.now()
      this.reprojectionFailures = 0

      return updates.length
    } catch (err) {
      this.reprojectionFailures++
      this.logger.error('Reprojection failed', {
        error: String(err),
        count,
        dim,
        failures: this.reprojectionFailures,
      })
      throw err
    }
  }

  /**
   * Backfill missing embeddings using the configured local embedding service.
   * Uses incremental projection (k-NN placement) when positions exist in DB,
   * avoiding expensive full reprojection.
   */
  async backfillEmbeddings(limit = 1000): Promise<{ embedded: number; reprojected: number; filamentEmbeddings: number }> {
    const embSvc = getEmbeddingService(this.logger)
    if (!embSvc.available) {
      throw new Error('Embedding service not available')
    }

    const missing = this.cortex.getEngramsWithoutEmbedding(limit)
    if (missing.length === 0) {
      return { embedded: 0, reprojected: 0, filamentEmbeddings: 0 }
    }

    // Ensure we have projection state for incremental placement
    // Try to restore from DB positions first (fast), only fall back to rebuild
    if (!this.projectionState) {
      this.projectionState = this._restoreProjectionState()
    }

    let embedded = 0
    let filamentEmbeddings = 0
    const positionUpdates: Array<{ id: string; x: number; y: number }> = []

    for (const { id, content } of missing) {
      const vec = await embSvc.embed(content, 'document')
      if (!vec) continue
      this.cortex.updateEngram(id, { embedding: vec })

      // Incremental projection: place via k-NN if we have state
      if (this.projectionState) {
        const pos = projectSingle(vec, this.projectionState)
        positionUpdates.push({ id, x: pos.x, y: pos.y })
      }
      embedded++

      const filEmbedded = await this.embedFilaments(id)
      filamentEmbeddings += filEmbedded
    }

    // Bulk update positions for efficiency
    if (positionUpdates.length > 0) {
      this.cortex.bulkUpdatePositions(positionUpdates)
    }

    // Only trigger full reprojection if:
    // 1. We still have no projection state (no valid positions existed in DB)
    // 2. AND we actually embedded something
    // This is rare - only happens on fresh/empty databases
    let reprojected = 0
    if (!this.projectionState && embedded > 0) {
      this.logger.info('No positions in DB - triggering full reprojection')
      reprojected = await this.reprojectAllAsync()
    }

    this.logger.info('Backfilled embeddings', {
      embedded,
      reprojected,
      filamentEmbeddings,
      incrementalPlacement: positionUpdates.length,
      remaining: this.cortex.countMissingEmbeddings(),
    })
    return { embedded, reprojected, filamentEmbeddings }
  }

  /**
   * Run kindling: seed activation → spreading excitation → ignition → Luminal Set.
   * This is the primary retrieval mechanism — associative, topology-aware.
   */
  kindle(
    embedding: number[] | null,
    textQuery: string | null,
    options?: KindlingOptions,
  ): LuminalSet {
    const result = this.kindlingEngine.kindle(embedding, textQuery, options)

    if (this.corticalField && result.engrams.length > 0) {
      try {
        const topCharge = result.engrams[0].charge
        this.corticalField.signal('sensory', {
          type: 'perception',
          content: `Mnemic retrieval: ${result.engrams.length} engrams kindled (top charge ${topCharge.toFixed(2)}, ${result.iterationsUsed} iterations, ${result.durationMs}ms)`,
          author: 'mnemic-field',
          salience: Math.min(0.7, topCharge * 0.5),
          tags: ['mnemic-retrieval'],
          structured: {
            engramCount: result.engrams.length,
            seedCount: result.seedCount,
            totalCharge: result.totalCharge,
            sparkPoint: result.sparkPoint,
            taskComplexity: result.taskComplexity,
          },
        })
      } catch { /* fire-and-forget — cortex issue should not block retrieval */ }
    }

    return result
  }

  /**
   * Post-task: record activation spikes for all engrams in the Luminal Set,
   * and drift co-activated engrams toward each other.
   */
  recordActivation(
    luminalSet: LuminalSet,
    taskContext?: string,
    outcome?: SpikeOutcome,
  ): void {
    this.kindlingEngine.recordActivation(luminalSet, taskContext, outcome)

    this.affectRegister.absorbActivation(
      luminalSet.engrams.map(e => ({
        affect: (e.engram.metadata?.affect as { valence: number; arousal: number } | undefined) ?? null,
        charge: e.charge,
      })),
      outcome,
    )
  }


  enableNeuralKindling(config?: Partial<NeuralKindlingConfig>): void {
    this.kindlingEngine.setNeuralConfig({ enabled: true, ...config })
    this.logger.info('Neural kindling enabled', { config: this.kindlingEngine.getNeuralConfig() })
  }

  disableNeuralKindling(): void {
    this.kindlingEngine.setNeuralConfig({ enabled: false })
    this.logger.info('Neural kindling disabled')
  }

  isNeuralKindlingEnabled(): boolean {
    return this.kindlingEngine.getNeuralConfig().enabled
  }

  /** Initialize ANN indexes (async, should be called after startup) */
  async initializeAnn(): Promise<void> {
    await this.kindlingEngine.initializeAnn()
  }

  /** Check if ANN indexes are ready */
  isAnnReady(): boolean {
    return this.kindlingEngine.isAnnReady()
  }

  /** Get ANN index statistics */
  getAnnStats(): { engram: { vectorCount: number; needsRebuild: boolean } | null; filament: { vectorCount: number; needsRebuild: boolean } | null } {
    return this.kindlingEngine.getAnnStats()
  }

  /** Force rebuild ANN indexes */
  async rebuildAnn(): Promise<void> {
    await this.kindlingEngine.rebuildAnn()
  }

  /**
   * Store a gradient request linking enrichment feedback to the last forward trace.
   * Called from the feedback handler to accumulate learning signals for consolidation.
   */
  recordEnrichFeedback(feedback: Record<string, boolean>): boolean {
    const trace = this.kindlingEngine.getLastTrace()
    if (!trace) return false

    try {
      this.cortex.storeGradientRequest(trace.id, feedback)
      this.logger.debug('Gradient request stored', {
        traceId: trace.id,
        feedbackCount: Object.keys(feedback).length,
      })
      return true
    } catch (err) {
      this.logger.warn('Failed to store gradient request', { error: err })
      return false
    }
  }

  getForwardTraceCount(): number {
    return this.cortex.forwardTraceCount()
  }

  getPendingGradientCount(): number {
    return this.cortex.pendingGradientCount()
  }

  getOptimizerStateCount(): number {
    return this.cortex.optimizerStateCount()
  }

  getBackpropConfig(): BackpropConfig {
    return this.gradientEngine.getConfig()
  }

  setBackpropConfig(config: Partial<BackpropConfig>): void {
    this.gradientEngine.setConfig(config)
    this.logger.info('Backprop config updated', { config: this.gradientEngine.getConfig() })
  }

  pruneOldTraces(maxAgeMs?: number): number {
    const maxAge = maxAgeMs ?? this.kindlingEngine.getNeuralConfig().maxTraceAge
    return this.cortex.pruneOldTraces(maxAge)
  }

  /**
   * Run a full consolidation cycle: radiance (potentiation recomputation),
   * co-activation drift, nucleus detection, spike history pruning,
   * and gradient-based synapse weight learning from enrichment feedback.
   *
   * Async — yields to the event loop between phases to prevent blocking
   * heartbeats and IPC when processing large datasets.
   */
  async consolidate(options?: ConsolidationOptions): Promise<ConsolidationResult> {
    return this.consolidationEngine.consolidate(options)
  }

  getFilaments(engramId: string): Filament[] {
    return this.filamentCortex.getFilamentsByEngram(engramId)
  }

  async embedFilaments(engramId: string): Promise<number> {
    const embSvc = getEmbeddingService(this.logger)
    if (!embSvc.available) return 0

    const filaments = this.filamentCortex.getFilamentsByEngram(engramId)
    const toEmbed = filaments.filter(f => f.embedding === null)
    if (toEmbed.length === 0) return 0

    const texts = toEmbed.map(f => f.content)
    const embeddings = await embSvc.embedBatch(texts, 'document')

    let embedded = 0
    for (let i = 0; i < toEmbed.length; i++) {
      if (embeddings[i]) {
        this.filamentCortex.updateFilamentEmbedding(toEmbed[i].id, embeddings[i]!)
        embedded++
      }
    }

    return embedded
  }

  async backfillFilaments(batchSize = 100): Promise<{ segmented: number; embedded: number; linked: number }> {
    const engramIds = this.filamentCortex.getEngramIdsWithoutFilaments(batchSize)
    let segmented = 0
    let embedded = 0
    let linked = 0

    for (const id of engramIds) {
      const engram = this.cortex.getEngram(id)
      if (!engram) continue

      const spans = segmentEngram(engram.content, engram.nodeType)
      if (spans.length === 0) continue

      const filaments = this.filamentCortex.createFilamentsBatch(
        spans.map(s => ({
          engramId: engram.id,
          spanStart: s.spanStart,
          spanEnd: s.spanEnd,
          content: s.content,
        }))
      )
      segmented += filaments.length

      const linkResult = this.entityLinker.linkFilaments(filaments)
      linked += linkResult.synapses

      const embResult = await this.embedFilaments(engram.id)
      embedded += embResult
    }

    this.logger.info('Filament backfill complete', { engrams: engramIds.length, segmented, embedded, linked })
    return { segmented, embedded, linked }
  }

  /**
   * Get the underlying Cortex for direct operations.
   * Prefer using MnemicField methods; use this for advanced/batch operations.
   */
  getCortex(): Cortex {
    return this.cortex
  }

  getChains(engramIds?: string[]): FilamentChain[] {
    return extractChains(this.filamentCortex, engramIds)
  }

  getCrystallization(filamentIds?: number[]): CrystallizationScore[] {
    return scoreCrystallization(this.filamentCortex, filamentIds)
  }

  getExpertiseMetrics(): ExpertiseMetrics[] {
    return computeExpertiseMetrics(this.filamentCortex, this.cortex)
  }

  getStaleDependents(supersededFilamentId: number): number[] {
    return propagateStaleness(this.filamentCortex, supersededFilamentId)
  }

  renderContext(
    query: string,
    options: RenderOptions & KindlingOptions,
  ): { entries: ZoomEntry[]; totalTokens: number } {
    const luminal = this.kindle(null, query, options)
    return renderWithZoom(luminal.engrams, luminal.filamentAnnotations, this.filamentCortex, options)
  }

  buildDelegationContext(
    query: string,
    options: RenderOptions & KindlingOptions,
  ): DelegationContext {
    const luminal = this.kindle(null, query, options)
    const rendered = renderWithZoom(luminal.engrams, luminal.filamentAnnotations, this.filamentCortex, options)
    const renderedText = rendered.entries.map(e => e.rendered).join('\n\n')

    const contradictions: Array<{ claimA: string; claimB: string; engramIds: [string, string] }> = []
    if (luminal.filamentAnnotations) {
      for (const ann of luminal.filamentAnnotations) {
        const synapses = this.filamentCortex.getFilamentSynapsesFrom(ann.filamentId)
        for (const syn of synapses) {
          if (syn.edgeType === 'contradicts') {
            const target = this.filamentCortex.getFilament(syn.targetId)
            if (target) {
              contradictions.push({
                claimA: ann.content,
                claimB: target.content,
                engramIds: [ann.engramId, target.engramId],
              })
            }
          }
        }
      }
    }

    return {
      renderedText,
      filamentGraph: {
        matchedFilaments: luminal.filamentAnnotations ?? [],
        chains: rendered.chains,
        contradictions,
      },
    }
  }

  setLlmProvider(provider: IProvider): void {
    this.filamentAnalyzer = new FilamentAnalyzer(
      this.filamentCortex, this.cortex, provider, this.logger,
    )
  }

  async runTier3Analysis(): Promise<{ callsMade: number; synapsesCreated: number }> {
    if (!this.filamentAnalyzer) return { callsMade: 0, synapsesCreated: 0 }
    return this.filamentAnalyzer.runTier3()
  }

  /**
   * Get the underlying FilamentCortex for direct operations.
   * Prefer using MnemicField methods; use this for advanced/batch operations.
   */
  getFilamentCortex(): FilamentCortex {
    return this.filamentCortex
  }

  getAffect(): AffectState {
    return this.affectRegister.getState()
  }

  absorbAffectSignal(signal: { valence?: number; arousal?: number }): void {
    this.affectRegister.absorbSignal(signal)
  }

  getAffectRegister(): AffectRegister {
    return this.affectRegister
  }

  setCorticalField(cortex: CorticalField): void {
    this.corticalField = cortex
  }

  close(): void {
    this.cortex.close()
    this.logger.info('Mnemic Field closed')
  }
}
