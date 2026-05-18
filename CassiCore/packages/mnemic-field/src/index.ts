import Database from 'better-sqlite3'
import fs from 'node:fs'
import path from 'node:path'
import { randomUUID } from 'node:crypto'
import type { DreamEngine } from '../memory-bridge/dream-engine.js'
import type { ILogger } from '../../../types/interfaces.js'
import { getEmbeddingService } from '../embeddings/embedding-service.js'
import { getRerankerService } from '../embeddings/reranker-service.js'
import { getDataDir } from '../../utils/paths.js'
import { Cortex, cosineSimilarity, computeSpikeImportance, computeAlpha } from './cortex.js'
import { KindlingEngine } from './kindling.js'
import { ConsolidationEngine } from './consolidation.js'
import { GradientEngine } from './backpropagation.js'
import { MigrationJobStore, type MigrationJobRecord, type MigrationJobSpec } from './migration-jobs.js'
import { migrateChunk, migrateMemoryAndArchives, migrateMemoryOnly } from './migrate-memory.js'
import { AttractorManager, normalizeTheta, SECTOR_SIZE, DEFAULT_SECTOR_COUNT } from './attractor.js'
import { VQSectorPrototypes } from './vq-prototypes.js'
import type { ConsolidationResult, ConsolidationOptions } from './consolidation.js'
import { projectTo2D, projectTo2DAsync, projectTo2DFromSAB, projectSingle, buildProjectionState, type ProjectionState } from './umap.js'
import { attune, AffectRegister, affectSimilarity } from './affect.js'
import type { AffectState, LightningRetrievalMode, RerankerMode } from './types.js'
import type { RetrievalLabelTriple } from '../reverie/retrieval-labeler-types.js'
import type { CorticalField } from '../cortex/index.js'
import type { IProvider } from '../../../types/runtime.js'
import { LLMReranker, type LLMRerankerConfig } from './llm-reranker.js'
import { LightningIndexer } from './lightning-indexer.js'
import { RELATIONAL_PHRASE_EDGE_TYPES, classifyEdge, RELATIONAL_PHRASES, classifyWithPhrases, type PhrasePrototypeSet, type ClassificationResult, EDGE_RELATORS_PHRASE_SET } from './edge-relators.js'
import { SIGNAL_TYPE_PHRASES, EPISTEMIC_SHIFT_PHRASES, WORK_UNIT_ANNOTATION_PHRASES } from '../phrase-prototypes.js'
import type {
  Engram, EngramCreate, EngramUpdate,
  MnemicSynapse, SynapseCreate,
  ActivationSpike, SpikeCreate,
  Nucleus, NucleusCreate,
  SpatialQuery, EngramSearchResult, TensionPair, TensionReport, FieldStats, MnemicRetrievalHit,
  TaskComplexity, LuminalSet, KindlingOptions, SpikeOutcome, ChargedEngram,
  EngramPosition,
  NeuralKindlingConfig,
  BackpropConfig,
  ReplayTraversal, ReplayTraversalOptions,
  ReplayEvent, ReplayEventKind, SessionReplaySummary,
} from './types.js'
import { SPARK_POINT_DEFAULTS, POTENTIATION_DEFAULTS } from './types.js'

const REPROJECTION = {
  cooldownMs: 30 * 60 * 1000,    // 30 min between runs
  maxFailures: 2,                 // block after this many consecutive failures
} as const

/** Strip conversation preamble from engram content so the reranker sees actual text.
 *  26% of embedded engrams start with "USER: (context)\\n\\nASSISTANT:" — their first
 *  500 chars are metadata, not content. This extracts from the first ASSISTANT: line. */
function stripConversationPreamble(content: string): string {
  // Conversation format: "USER: ...\\n\\nASSISTANT: actual content"
  const assistantMatch = content.match(/\nASSISTANT:\s*/)
  if (assistantMatch && assistantMatch.index !== undefined) {
    const afterAssistant = content.slice(assistantMatch.index + assistantMatch[0].length)
    if (afterAssistant.length > 50) return afterAssistant
  }
  // Also handle "USER: continue\\nASSISTANT:" variant
  const altMatch = content.match(/\nASSISTANT:\s*/)
  if (altMatch && altMatch.index !== undefined && altMatch.index > 5) {
    const after = content.slice(altMatch.index + altMatch[0].length)
    if (after.length > 50) return after
  }
  return content
}

function kindlingHit(hit: ChargedEngram): MnemicRetrievalHit {
  return {
    id: hit.engram.id,
    content: hit.engram.content,
    nodeType: hit.engram.nodeType,
    score: hit.charge,
    charge: hit.charge,
    potentiation: hit.engram.potentiation,
    provenance: hit.engram.provenance,
    tags: hit.engram.tags,
    metadata: hit.engram.metadata,
  }
}

function compareReplayEngrams(a: Engram, b: Engram): number {
  const byT = a.t - b.t
  if (byT !== 0) return byT
  const byCreatedAt = a.createdAt.localeCompare(b.createdAt)
  if (byCreatedAt !== 0) return byCreatedAt
  return a.id.localeCompare(b.id)
}

function compareReplayEvents(a: ReplayEvent, b: ReplayEvent): number {
  const byTimestamp = a.timestamp.localeCompare(b.timestamp)
  if (byTimestamp !== 0) return byTimestamp
  return a.id.localeCompare(b.id)
}

function replayKindForId(id: string): ReplayEventKind {
  if (id.startsWith('session:')) return 'session'
  if (id.startsWith('run:')) return 'run'
  if (id.startsWith('step:')) return 'step'
  if (id.startsWith('turn:')) return 'turn'
  if (id.startsWith('tc:')) return 'tool_call'
  if (id.startsWith('tr:')) return 'tool_result'
  if (id.startsWith('session_result:')) return 'session_result'
  if (id.startsWith('session_summary:')) return 'session_summary'
  if (id.startsWith('err:')) return 'error'
  if (id.startsWith('artifact:')) return 'artifact'
  return 'unknown'
}

function shouldIncludeReplayEvent(rootId: string, candidateId: string): boolean {
  if (candidateId === rootId) return true
  if (rootId.startsWith('session:') && candidateId.startsWith('session:')) return false
  if (rootId.startsWith('run:') && candidateId.startsWith('run:')) return false
  return true
}

function synapseKey(synapse: MnemicSynapse): string {
  return `${synapse.sourceId}\u0000${synapse.targetId}\u0000${synapse.edgeType}`
}

export { Cortex } from './cortex.js'
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
export { GraphAttnPropagator } from './graph-attn-propagator.js'
export type { PropagatedEngram, PropagationPath, PropagationHop, GraphAttnPropagatorOpts } from './graph-attn-propagator.js'
export { VQSectorPrototypes, cosineSimilarity, cosineDistance } from './vq-prototypes.js'
export type { AssignResult } from './vq-prototypes.js'
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
  Affect, AffectState, AffectLabel, AffectConfig,
  NeuralKindlingConfig, ForwardTrace, ForwardRecord, GradientRequest,
  BackpropConfig, BackpropResult, TraceGradientResult, SynapseOptimizerState,
  ExpertKind, ExpertDomain, ExpertProvenance, ExpertMetadata,
  ExpertLifecycleState, ExpertQuery, TraceOptions, TraceEvent,
  PrimedNucleus, BroadcastResult,
} from './types.js'
export {
  ENGRAM_TYPES, SYNAPSE_TYPES, SYNAPSE_PROPAGATION,
  POTENTIATION_DEFAULTS, SPARK_POINT_DEFAULTS, KINDLING_DEFAULTS,
  AFFECT_DEFAULTS, BACKPROP_DEFAULTS,
} from './types.js'
export { attune, AffectRegister, resolveLabel, affectSimilarity, emotionalIntensity } from './affect.js'
export { classifyWithPhrases, EDGE_RELATORS_PHRASE_SET } from './edge-relators.js'
export type { PhrasePrototypeSet, ClassificationResult } from './edge-relators.js'

export class MnemicField {
  private cortex: Cortex
  private kindlingEngine: KindlingEngine
  private consolidationEngine: ConsolidationEngine
  private gradientEngine: GradientEngine
  /** Attentional focus — tonic center (Pineal facets at origin) + phasic (session context). */
  readonly attractor: AttractorManager
  /** VQ Sector Prototypes for automatic domain discovery beyond Pineal domains. */
  readonly vqPrototypes: VQSectorPrototypes
  private migrationJobs: MigrationJobStore
  private logger: ILogger
  private projectionState: ProjectionState | null = null
  private reprojectionInFlight: Promise<number> | null = null
  private reprojectionFailures = 0
  private lastReprojectionAt = 0
  private affectRegister: AffectRegister

  // LLM-based reranker (alternative to filament kindling). Set via setRerankerProvider.
  private reranker: LLMReranker | null = null
  private rerankerModel: string = 'github-copilot/gpt-5-mini'
  private rerankerMode: RerankerMode = 'local'
  private lightningIndexer: LightningIndexer | null = null
  // Cached after each retrieve() so recordEnrichFeedback can convert
  // helpful/unhelpful into Lightning Indexer training triples without a
  // round-trip to lightning_retrieval_events.
  private lastRetrievalId: string | null = null
  private lastRetrievalCandidates: string[] = []
  private lastRetrievalIndexerScores: Float32Array | null = null
  private lastRetrievalRerankerScores: Float32Array | null = null
  private lightningShadowEnabled: boolean = false
  private rerankerEnabled: boolean = false
  private foreshadow: { observe: (args: { query: string; sessionId?: string; wasCacheHit: boolean }) => Promise<void> } | null = null

  // Global Workspace Broadcast state (Phase 1)
  /** Nuclei currently primed by broadcast. In-memory only — lost on restart. */
  private primedNuclei: Map<string, import('./types.js').PrimedNucleus> = new Map()
  /** Resonance threshold for nucleus priming. */
  private broadcastResonanceThreshold = 0.3

  // Retrieval result cache. Kindling does 5 iterations of spreading activation
  // across ~800k filaments and takes 10-30s. Repeated identical queries (very
  // common during a single conversation turn — agent often calls enrich with
  // similar terms) can short-circuit. Cleared on store/insert and TTL-bounded.
  private retrieveCache = new Map<string, { hits: MnemicRetrievalHit[]; ts: number }>()
  private static readonly RETRIEVE_CACHE_TTL_MS = 5 * 60 * 1000  // 5 min
  private static readonly RETRIEVE_CACHE_MAX = 64

  /** Luminal engram IDs from the most recent retrieval — consumed by store()
   *  to annotate newly created engrams with their retrieval trigger chain. */
  private lastLuminalIds: string[] = []

  /** Harmony metric: 0=Yang-dominated (all lit), 1=Yin-dominated (all shadow).
   *  Computed during each kindling cycle and read by consolidation, DMN, and spark modulation. */
  private lastHarmony: number = 0.5

  /** Cached sector density: sector index → count of high-pot engrams.
   *  Precomputed during consolidation (see computeSectorDensity), read by computeHarmony. */
  private sectorDensityCache: Map<number, number> = new Map()

  /** Cached total count of engrams with theta metadata (valid field positions). */
  private validPositionCount: number = 0

  /** Counter for periodic attractor Yin phase (runs every N retrievals). */
  private yinPhaseCounter: number = 0
  private static readonly YIN_PHASE_INTERVAL = 10

  /** Enable the LLM reranker. Call during daemon startup after providers are wired. */
  setRerankerProvider(provider: IProvider, model?: string, enabled?: boolean): void {
    this.rerankerModel = model ?? this.rerankerModel
    this.rerankerEnabled = enabled ?? true
    if (this.rerankerEnabled && provider) {
      this.reranker = new LLMReranker(this.logger, {
        provider,
        model: this.rerankerModel,
        maxSentences: 120,
        maxSentenceChars: 400,
        source: 'mnemic.reranker',
      })
      this.logger.info('LLM reranker enabled', { model: this.rerankerModel })
    } else {
      this.reranker = null
      this.rerankerEnabled = false
      this.logger.info('LLM reranker disabled')
    }
  }

  setRerankerMode(mode: RerankerMode): void {
    this.rerankerMode = mode
    if (mode === 'off') {
      this.rerankerEnabled = false
      this.reranker = null
    } else if (mode === 'llm') {
      this.rerankerEnabled = !!this.reranker
    } else {
      this.rerankerEnabled = false
    }
    this.logger.info('MnemicField reranker mode set', { mode, llmAvailable: !!this.reranker })
  }

  setForeshadow(fs: { observe: (args: { query: string; sessionId?: string; wasCacheHit: boolean }) => Promise<void> } | null): void {
    this.foreshadow = fs
  }

  setLightningShadowMode(enabled: boolean): void {
    this.lightningShadowEnabled = enabled
    if (enabled && !this.lightningIndexer) {
      this.lightningIndexer = new LightningIndexer(this.cortex, this.logger)
    }
    this.logger.info('Lightning shadow mode', { enabled })
  }

  private corticalField?: CorticalField
  private dreamEngine: DreamEngine | null = null
  private db: Database.Database  // Store for persistence operations
  /** Cached edge classification phrase embeddings — built once at first call */
  private _phraseEmbeddings: Map<string, Float32Array> | null = null
  /** Generic phrase embedding cache keyed by prototype set identity */
  private _genericPhraseCaches: Map<string, Map<string, Float32Array>> = new Map()

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
    this.attractor = new AttractorManager()
    this.vqPrototypes = new VQSectorPrototypes(1024)  // matches Qwen3-Embedding-0.6B dim
    this.kindlingEngine = new KindlingEngine(this.cortex, logger)
    this.kindlingEngine.setAttractor(this.attractor)
    this.kindlingEngine.setHarmonyProvider(() => this.getHarmony())
    this.gradientEngine = new GradientEngine(this.cortex, logger)
    this.consolidationEngine = new ConsolidationEngine(this.cortex, logger, this.gradientEngine, null)
    this.consolidationEngine.setHarmonyProvider(() => this.getHarmony())
    this.migrationJobs = new MigrationJobStore(db)
    this.affectRegister = new AffectRegister()

    // Initialize projection state from existing positions in DB (if available)
    this.projectionState = this._restoreProjectionState()

    this.logger.info('Mnemic Field initialized', {
      projectionStateRestored: this.projectionState !== null,
      validPositions: this.cortex.countValidPositions(),
    })

    // Migrate bridge engrams from old 'pattern' nodeType to 'bridge'
    const migrated = this.cortex.migrateBridgeNodeTypes()
    if (migrated > 0) {
      this.logger.info('Migrated bridge engrams to nodeType bridge', { count: migrated })
    }
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

  // Radial position defaults: non-embedded engrams are placed at the periphery
  // so the origin (0,0) is reserved for high-importance engrams (Pineal facets,
  // self-model knowledge). Embedded engrams use UMAP projection until replaced
  // by VQ sector assignment (Phase 6 of radial/polar topology).
  private static readonly PERIPHERY_RADIUS_MIN = 0.85
  private static readonly PERIPHERY_RADIUS_MAX = 0.95

  /**
   * Store a new engram. Position assignment:
   * - Explicit x/y provided → use as-is (Pineal facets, self-model anchors)
   * - Embedding provided, no x/y → VQ Sector Prototypes assign domain-aware position
   * - No embedding, no x/y → random position at periphery (conversation transcripts, tools)
   */
  store(input: EngramCreate): Engram {
    // New engram → invalidate retrieve cache (results may now be stale).
    if (this.retrieveCache.size > 0) this.retrieveCache.clear()
    let x = input.x
    let y = input.y
    let r = input.r
    let theta = input.theta

    // Resolve position: x/y explicit → polar → VQ → periphery fallback
    if (input.x === undefined && input.y === undefined) {
      if (r !== undefined && theta !== undefined) {
        // Polar coordinates provided → convert to Cartesian
        x = r * Math.cos(theta)
        y = r * Math.sin(theta)
      } else if (r !== undefined && theta === undefined) {
        // Radial distance without angle — assign random angle
        theta = Math.random() * 2 * Math.PI
        x = r * Math.cos(theta)
        y = r * Math.sin(theta)
      } else if (input.embedding) {
        // Has embedding → VQ Sector Prototypes assign domain-aware θ and radial r
        const emb = input.embedding instanceof Float32Array
          ? input.embedding
          : new Float32Array(input.embedding)
        const { prototypeIdx, distance } = this.vqPrototypes.assign(emb)
        const assignedIdx = this.vqPrototypes.maybeCreatePrototype(emb)
        theta = this.vqPrototypes.prototypeAngle(assignedIdx)
        // Radial distance encodes semantic proximity to prototype
        // Close to prototype → near center (0.15); far → periphery (0.85)
        r = 0.15 + distance * 0.7
        x = r * Math.cos(theta)
        y = r * Math.sin(theta)
      } else {
        // No embedding → place at periphery with random angle.
        theta = Math.random() * 2 * Math.PI
        r = MnemicField.PERIPHERY_RADIUS_MIN
          + Math.random() * (MnemicField.PERIPHERY_RADIUS_MAX - MnemicField.PERIPHERY_RADIUS_MIN)
        x = r * Math.cos(theta)
        y = r * Math.sin(theta)
      }
    } else {
      // Explicit x/y provided — compute polar for metadata
      if (r === undefined) r = Math.sqrt(x! * x! + y! * y!)
      if (theta === undefined) theta = Math.atan2(y!, x!)
    }

    const affect = attune(input.content)
    let metadata: Record<string, unknown> = { ...input.metadata ?? {}, affect, r, theta }

    // Contrastive retrieval feedback: link new engrams to the luminal
    // engrams that triggered their creation via the most recent retrieval.
    if (this.lastLuminalIds.length > 0) {
      metadata = { ...metadata, triggeredBy: [...this.lastLuminalIds] }
      this.lastLuminalIds = []
    }

    const engram = this.cortex.createEngram({ ...input, x, y, metadata })
    return engram
  }

  get(id: string): Engram | null {
    return this.cortex.getEngram(id)
  }

  /**
   * Find engrams by exact provenance match.
   * Used for idempotent Pineal facet seeding and other provenance-based
   * deduplication. Returns empty array if none found.
   */
  searchByProvenance(provenance: string): Engram[] {
    return this.cortex.listEngrams(1000).filter(
      e => (e.provenance ?? '') === provenance
    )
  }

  /**
   * Find a file engram by its filePath.
   * Returns null if no file engram exists for the given path.
   */
  findFileByPath(filePath: string): Engram | null {
    return this.cortex.findFileByPath(filePath)
  }

  /**
   * Find all file_version engrams for a given filePath.
   * Returns all versions sorted by creation order.
   */
  findFileVersionsByPath(filePath: string): Engram[] {
    return this.cortex.findFileVersionsByPath(filePath)
  }

  /**
   * Prune stale file_read engrams older than a threshold.
   * Keeps at most keepPerPath latest reads per file path.
   * Default: 7 days, keep 3 latest reads per file.
   *
   * Call this periodically (via Thalamus session lifecycle or cron-like
   * cleanup) to prevent unbounded growth of file_read engrams.
   */
  pruneFileReads(olderThanMs?: number, keepPerPath?: number): number {
    return this.cortex.pruneFileReads(
      olderThanMs ?? 7 * 24 * 60 * 60 * 1000,
      keepPerPath ?? 3,
    )
  }

  update(id: string, update: EngramUpdate): Engram | null {
    // Convert polar to Cartesian when r/theta provided without x/y
    if (update.x === undefined && update.y === undefined
        && update.r !== undefined && update.theta !== undefined) {
      update = {
        ...update,
        x: update.r * Math.cos(update.theta),
        y: update.r * Math.sin(update.theta),
      }
    }
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

  getEngramsByIdPrefix(
    prefix: string,
    opts: { limit?: number; offset?: number; order?: 'asc' | 'desc' } = {},
  ): Engram[] {
    return this.cortex.getEngramsByIdPrefix(prefix, opts)
  }

  getEngramsBySessionId(sessionId: string, limit = 1000, offset = 0): Engram[] {
    return this.cortex.getEngramsBySessionId(sessionId, limit, offset)
  }

  getTypedSynapses(engramId: string, edgeType: string, direction: 'in' | 'out'): MnemicSynapse[] {
    return this.cortex.getTypedSynapses(engramId, edgeType, direction)
  }

  bulkUpdateSynapseWeights(updates: Array<{ sourceId: string; targetId: string; edgeType: string; weight: number }>): number {
    return this.cortex.bulkUpdateSynapseWeights(updates)
  }

  getReplayChildren(parentId: string, opts: { limit?: number } = {}): Engram[] {
    const limit = Math.max(1, Math.min(opts.limit ?? 500, 5000))
    return this.getTypedSynapses(parentId, 'part_of', 'in')
      .map(s => this.get(s.sourceId))
      .filter((engram): engram is Engram => Boolean(engram))
      .sort(compareReplayEngrams)
      .slice(0, limit)
  }

  getReplayTimeline(parentId: string, opts: { limit?: number } = {}): Engram[] {
    const children = this.getReplayChildren(parentId, opts)
    if (children.length <= 1) return children

    const childIds = new Set(children.map(e => e.id))
    const nextByPrevious = new Map<string, string>()
    const previousIds = new Set<string>()
    for (const child of children) {
      for (const synapse of this.getTypedSynapses(child.id, 'temporal_neighbor', 'out')) {
        if (!childIds.has(synapse.targetId)) continue
        nextByPrevious.set(child.id, synapse.targetId)
        previousIds.add(synapse.targetId)
      }
    }

    const start = children.find(e => !previousIds.has(e.id)) ?? children[0]
    const byId = new Map(children.map(e => [e.id, e]))
    const ordered: Engram[] = []
    const seen = new Set<string>()
    let current: Engram | undefined = start
    while (current && !seen.has(current.id)) {
      ordered.push(current)
      seen.add(current.id)
      current = byId.get(nextByPrevious.get(current.id) ?? '')
    }
    for (const child of children) {
      if (!seen.has(child.id)) ordered.push(child)
    }
    return ordered
  }

  getReplaySubgraph(rootId: string, opts: ReplayTraversalOptions = {}): ReplayTraversal {
    const root = this.get(rootId)
    if (!root) return { rootId, nodes: [], synapses: [] }
    const limit = Math.max(1, Math.min(opts.limit ?? 1000, 10_000))
    const nodeIds = new Set<string>([root.id])
    const queue = [root.id]
    const synapseMap = new Map<string, MnemicSynapse>()

    while (queue.length > 0 && nodeIds.size < limit) {
      const id = queue.shift()!
      const childEdges = this.getTypedSynapses(id, 'part_of', 'in')
      for (const synapse of childEdges) {
        synapseMap.set(synapseKey(synapse), synapse)
        if (!nodeIds.has(synapse.sourceId)) {
          nodeIds.add(synapse.sourceId)
          if (opts.includeRecursive !== false) queue.push(synapse.sourceId)
        }
      }
    }

    for (const id of [...nodeIds]) {
      for (const synapse of this.getTypedSynapses(id, 'caused_by', 'in')) {
        synapseMap.set(synapseKey(synapse), synapse)
        if (nodeIds.size < limit) nodeIds.add(synapse.sourceId)
      }
      for (const synapse of this.getTypedSynapses(id, 'led_to', 'out')) {
        synapseMap.set(synapseKey(synapse), synapse)
        if (nodeIds.size < limit) nodeIds.add(synapse.targetId)
      }
      for (const synapse of this.getTypedSynapses(id, 'spawned_from', 'out')) {
        synapseMap.set(synapseKey(synapse), synapse)
        if (nodeIds.size < limit) nodeIds.add(synapse.targetId)
      }
      for (const synapse of this.getTypedSynapses(id, 'supersedes', 'out')) {
        synapseMap.set(synapseKey(synapse), synapse)
        if (nodeIds.size < limit) nodeIds.add(synapse.targetId)
      }
    }

    for (const id of [...nodeIds]) {
      for (const edgeType of ['temporal_neighbor', 'caused_by', 'spawned_from', 'led_to', 'supersedes'] as const) {
        for (const synapse of this.getTypedSynapses(id, edgeType, 'out')) {
          if (nodeIds.has(synapse.targetId)) synapseMap.set(synapseKey(synapse), synapse)
        }
      }
    }

    const synapses = [...synapseMap.values()]
    const nodes = [...nodeIds]
      .map(id => this.get(id))
      .filter((engram): engram is Engram => Boolean(engram))
      .sort(compareReplayEngrams)
      .map(engram => {
        const related = synapses.filter(s => s.sourceId === engram.id || s.targetId === engram.id)
        return {
          engram,
          parentIds: related.filter(s => s.sourceId === engram.id && s.edgeType === 'part_of').map(s => s.targetId),
          childIds: related.filter(s => s.targetId === engram.id && s.edgeType === 'part_of').map(s => s.sourceId),
          previousIds: related.filter(s => s.targetId === engram.id && s.edgeType === 'temporal_neighbor').map(s => s.sourceId),
          nextIds: related.filter(s => s.sourceId === engram.id && s.edgeType === 'temporal_neighbor').map(s => s.targetId),
        }
      })

    return { rootId, nodes, synapses }
  }

  replaySession(sessionId: string, opts: ReplayTraversalOptions = {}): ReplayEvent[] {
    const rootId = sessionId.startsWith('session:') ? sessionId : `session:${sessionId}`
    return this.replayFromRoot(rootId, opts)
  }

  replayRun(runId: string, opts: ReplayTraversalOptions = {}): ReplayEvent[] {
    const rootId = runId.startsWith('run:') ? runId : `run:${runId}`
    return this.replayFromRoot(rootId, opts)
  }

  getSessionSummary(sessionId: string): SessionReplaySummary {
    const rootId = sessionId.startsWith('session:') ? sessionId : `session:${sessionId}`
    const root = this.get(rootId)
    if (!root) {
      return {
        sessionId: rootId,
        exists: false,
        eventCount: 0,
        turnCount: 0,
        runCount: 0,
        stepCount: 0,
        toolCallCount: 0,
        toolResultCount: 0,
        anomalyCount: 0,
        artifactCount: 0,
        startedAt: null,
        lastEventAt: null,
      }
    }

    const events = this.replaySession(rootId)
    const timestamps = events.map(e => e.timestamp).sort()
    return {
      sessionId: rootId,
      exists: true,
      eventCount: events.length,
      turnCount: events.filter(e => e.kind === 'turn').length,
      runCount: events.filter(e => e.kind === 'run').length,
      stepCount: events.filter(e => e.kind === 'step').length,
      toolCallCount: events.filter(e => e.kind === 'tool_call').length,
      toolResultCount: events.filter(e => e.kind === 'tool_result').length,
      anomalyCount: events.filter(e => e.kind === 'error').length,
      artifactCount: events.filter(e => e.kind === 'artifact').length,
      startedAt: timestamps[0] ?? root.createdAt,
      lastEventAt: timestamps[timestamps.length - 1] ?? root.createdAt,
    }
  }

  private replayFromRoot(rootId: string, opts: ReplayTraversalOptions): ReplayEvent[] {
    const graph = this.getReplaySubgraph(rootId, opts)
    return graph.nodes
      .filter(node => shouldIncludeReplayEvent(rootId, node.engram.id))
      .map(node => ({
        id: node.engram.id,
        kind: replayKindForId(node.engram.id),
        nodeType: node.engram.nodeType,
        timestamp: node.engram.createdAt,
        content: node.engram.content,
        metadata: node.engram.metadata,
        parentIds: node.parentIds,
        childIds: node.childIds,
        previousIds: node.previousIds,
        nextIds: node.nextIds,
      }))
      .sort((a, b) => {
        if (a.id === rootId && b.id !== rootId) return -1
        if (b.id === rootId && a.id !== rootId) return 1
        return compareReplayEvents(a, b)
      })
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
    const results = this.cortex.searchText(query, limit)
    return results.filter(r => r.engram.nodeType !== 'bridge')
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
    return this.cortex.stats()
  }

/**
   * Primary retrieval API for runtime consumers.
   * Uses kindling first, falls back to text search when needed.
   * 
   * Generates query embedding so filament ANN search is used.
   */
  async retrieve(
    query: string,
    options?: KindlingOptions & { limit?: number; sessionId?: string },
  ): Promise<MnemicRetrievalHit[]> {
    const limit = options?.limit ?? options?.maxLuminalSize ?? 8

    // Cache check — see RETRIEVE_CACHE notes on the class field.
    // Key on all parameters that change the result, including affect state.
    const affectHash = options?.currentAffect
      ? `${options.currentAffect.valence}|${options.currentAffect.arousal}`
      : ''
    const cacheKey = `${query}\\u0000${limit}\\u0000${options?.complexity ?? ''}\\u0000${options?.maxIterations ?? ''}\\u0000${affectHash}`
    const now = Date.now()
    const cached = this.retrieveCache.get(cacheKey)
    const wasCacheHit = !!(cached && (now - cached.ts) < MnemicField.RETRIEVE_CACHE_TTL_MS)
    this.foreshadow?.observe({ query, sessionId: options?.sessionId, wasCacheHit }).catch(() => { /* never blocks retrieve */ })
    if (wasCacheHit) {
      this.retrieveCache.delete(cacheKey)
      this.retrieveCache.set(cacheKey, cached!)
      return cached!.hits
    }

    // Retrieval event ID — fresh on each cache miss so Reverie can correlate
    // candidates with the primary's subsequent tool-round behavior.
    const retrievalId = randomUUID()
    const sessionId = options?.sessionId

    // Generate embedding for query.
    const embSvc = getEmbeddingService(this.logger)
    const queryEmbedding = embSvc.available ? await embSvc.embed(query, 'query') : null

    let hits: MnemicRetrievalHit[] = []

    // Step 1: Kindling generates candidate engrams via engram ANN + synapse spread.
    // This is the "candidate generation" phase — no filaments involved.
    const luminal = this.kindle(queryEmbedding, query, {
      ...options,
      maxLuminalSize: limit * 3,  // grab more candidates, then trim after ranking
      maxIterations: 2,            // spread activation — now batch-optimized (2-3 queries/iter)
      maxSeeds: Math.max(options?.maxSeeds ?? 20, limit * 4),
      includeText: true,
      currentAffect: options?.currentAffect ?? this.affectRegister.getAffect(),
    })

    // Track luminal engram IDs for retrieval chain continuity.
    // New engrams created this turn will carry triggeredBy metadata
    // linking them to the engrams that triggered their creation.
    this.lastLuminalIds = luminal.engrams.map(e => e.engram.id)

    // Compute harmony metric after each kindling cycle
    // (feeds into spark point modulation, consolidation, and DMN observation)
    try {
      this.computeHarmony()
    } catch { /* never block retrieval for harmony failures */ }

    // Periodic Yin phase: acknowledge neglected sectors
    try {
      this.yinPhaseCounter++
      if (this.yinPhaseCounter >= MnemicField.YIN_PHASE_INTERVAL) {
        this.logger.info('Attractor Yin phase — trigger', { counter: this.yinPhaseCounter })
        this.yinPhaseCounter = 0
        if (this.sectorDensityCache.size === 0) this.computeSectorDensity()
        const sector = this.attractor.attractorYinPhase(this.sectorDensityCache)
        if (sector >= 0) {
          this.logger.info('Attractor Yin phase — acknowledged shadow sector', { sector, theta: `${(sector * 30)}°–${((sector + 1) * 30)}°` })
        } else {
          this.logger.info('Attractor Yin phase — nothing to nudge', { reason: sector === -1 ? 'no candidates' : 'min visits > 10' })
        }
      }
    } catch (err) { /* never block retrieval for Yin phase failures */
      this.logger.warn('Attractor Yin phase failed', { error: String(err) })
    }

    let lightningRanked: Array<{ engramId: string; score: number }> | null = null

    if (luminal.engrams.length === 0) {
      hits = this.searchText(query, limit).map(r => ({
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
    } else {
      const candidates = luminal.engrams.map(hit => hit.engram)

      // Lightning shadow mode: score candidates with the learned indexer,
      // log overlap with the final ranking. Does not affect retrieval output.
      if (this.lightningShadowEnabled && this.lightningIndexer && queryEmbedding) {
        try {
          const idxCandidates = candidates
            .filter(e => e.embedding && e.embedding.length > 0)
            .map(e => ({ engramId: e.id, embedding: e.embedding as Float32Array }))
          if (idxCandidates.length > 0) {
            lightningRanked = this.lightningIndexer.score(
              new Float32Array(queryEmbedding),
              idxCandidates,
            )
          }
        } catch (err) {
          this.logger.debug('Lightning shadow score failed', { error: String(err) })
        }
      }

      // Step 2: Rerank candidates using the configured reranker mode.
      // - 'local': cross-encoder available for tool-result distillation, but for
      //   engram retrieval we use kindling charges directly — the BGE cross-encoder
      //   penalizes investigative/conversational framing common in session transcripts
      //   (cosine similarity 0.65 drops to 0.09 for "let me look at the file...").
      // - 'llm': cloud LLM picks relevant sentences, ~1-2s, produces excerpts
      // - 'off': use kindling charge-based ranking directly
      if (this.rerankerMode === 'local') {
        // Use kindling charges directly — the ANN cosine similarity is a better
        // relevance signal for conversational engrams than the cross-encoder.
        hits = luminal.engrams
          .map(hit => kindlingHit(hit))
          .sort((a, b) => b.score - a.score)
          .slice(0, limit)
      } else if (this.rerankerMode === 'llm' && this.reranker) {
        try {
          const ranked = await this.reranker.rerank(query, candidates, limit, undefined)
          if (ranked.length > 0) {
            hits = LLMReranker.toRetrievalHits(candidates, ranked, limit)
          } else {
            hits = luminal.engrams.map(hit => kindlingHit(hit))
          }
        } catch (err) {
          this.logger.warn('LLM reranker failed, using kindling charges', { error: String(err) })
          hits = luminal.engrams.map(hit => kindlingHit(hit))
        }
      } else {
        hits = luminal.engrams.map(hit => kindlingHit(hit))
      }
    }

    if (lightningRanked && lightningRanked.length > 0) {
      const k = Math.min(limit, lightningRanked.length, hits.length)
      if (k > 0) {
        const finalTopK = new Set(hits.slice(0, k).map(h => h.id))
        const lightningTopK = lightningRanked.slice(0, k).map(r => r.engramId)
        let overlap = 0
        for (const id of lightningTopK) if (finalTopK.has(id)) overlap++
        this.logger.info('Lightning shadow overlap', {
          k,
          overlap,
          overlapRatio: overlap / k,
          lightningTopScore: lightningRanked[0]?.score ?? 0,
          candidateCount: lightningRanked.length,
        })
      }
    }

    // Persist a retrieval event so Reverie can later label it from the
    // primary's downstream tool-round behavior. Best-effort — failures must
    // never block the retrieve path.
    try {
      const candidateIds = hits.map(h => h.id)
      const indexerScoresArr = lightningRanked
        ? new Float32Array(candidateIds.map(id => {
            const entry = lightningRanked!.find(r => r.engramId === id)
            return entry ? entry.score : 0
          }))
        : undefined

      const rerankerScoresArr = this.rerankerMode === 'local'
        ? new Float32Array(hits.map(h => h.score))
        : hits.length > 0
          ? new Float32Array(hits.map((_, i) => 1 - (i / hits.length)))
          : undefined

      const mode: LightningRetrievalMode = this.rerankerMode === 'local'
        ? (lightningRanked ? 'shadow' : 'kindle-only')
        : lightningRanked ? 'shadow' : (this.rerankerMode === 'llm' ? 'shadow' : 'kindle-only')

      this.lastRetrievalId = retrievalId
      this.lastRetrievalCandidates = candidateIds
      this.lastRetrievalIndexerScores = indexerScoresArr ?? null
      this.lastRetrievalRerankerScores = rerankerScoresArr ?? null

      this.cortex.recordLightningRetrievalEvent({
        retrievalId,
        sessionId,
        queryText: query,
        queryEmbedding: queryEmbedding ? new Float32Array(queryEmbedding) : undefined,
        candidateIds,
        indexerScores: indexerScoresArr,
        rerankerScores: rerankerScoresArr,
        indexerVersion: this.lightningIndexer?.stats().version,
        mode,
        createdAt: new Date().toISOString(),
      })

      for (const h of hits) {
        h.metadata = { ...(h.metadata ?? {}), retrievalId }
      }
    } catch (err) {
      this.logger.debug('Failed to persist retrieval event', { error: String(err) })
    }

    // Filter bridge engrams from results — they're structural, not content.
    const contentHits = hits.filter(h => h.nodeType !== 'bridge')

    // Cache result. Evict oldest if over capacity (Map iteration order is insertion order).
    this.retrieveCache.set(cacheKey, { hits: contentHits, ts: now })
    while (this.retrieveCache.size > MnemicField.RETRIEVE_CACHE_MAX) {
      const oldest = this.retrieveCache.keys().next().value
      if (oldest === undefined) break
      this.retrieveCache.delete(oldest)
    }
    return contentHits
  }

  /**
   * Precompute engram density per angular sector.
   * Fast DB scan counting high-potentiation engrams in each 30° sector.
   * Called periodically during consolidation. Results cached in sectorDensityCache.
   */
  computeSectorDensity(sectorCount: number = DEFAULT_SECTOR_COUNT): Map<number, number> {
    const density = new Map<number, number>()
    const secSize = (2 * Math.PI) / sectorCount
    const highPotThreshold = 0.3

    // Query engrams with potentiation > threshold AND a known position
    // (either explicit theta in metadata, or x/y coords we can derive theta from).
    const rows = this.db.prepare(`
      SELECT
        x, y,
        json_extract(metadata, '$.theta') AS metaTheta
      FROM engrams
      WHERE potentiation > ?
        AND (
          json_extract(metadata, '$.theta') IS NOT NULL
          OR (x IS NOT NULL AND x != 0 AND y IS NOT NULL AND y != 0)
        )
    `).all(highPotThreshold) as Array<{ x: number | null; y: number | null; metaTheta: number | null }>

    for (const row of rows) {
      const theta = row.metaTheta ?? Math.atan2(row.y ?? 0, row.x ?? 0)
      const sector = Math.floor(normalizeTheta(theta) / secSize) % sectorCount
      density.set(sector, (density.get(sector) ?? 0) + 1)
    }

    this.sectorDensityCache = density
    this.validPositionCount = rows.length
    const maxVal = density.size > 0 ? Math.max(...density.values()) : 0
    this.logger.info('Sector density recomputed', {
      sectorCount,
      totalEngrams: rows.length,
      maxDensity: maxVal,
    })
    return density
  }

  /**
   * Compute the harmony metric: 0=Yang-dominated (all lit), 1=Yin-dominated (all shadow).
   *
   * Two components:
   *   yinRatio  — what fraction of high-pot engrams are NOT in recent luminal sets?
   *   coverageRatio — what fraction of sectors-with-engrams have been visited?
   *
   * Weighted blend: 0.4 * yinRatio + 0.6 * coverageRatio (emphasizes structural).
   * Called during each kindling cycle via computeGlobalSparkPoint().
   */
  computeHarmony(): number {
    const sectorCount = 12

    // Ensure density is computed (does full scan only on first call)
    if (this.sectorDensityCache.size === 0) {
      this.computeSectorDensity(sectorCount)
    }

    // Use cached position count as proxy for high-pot count
    const highPotCount = Math.max(1, this.validPositionCount)

    // Yin ratio: what fraction of positioned engrams are NOT in the luminal set?
    const recentAvgLuminalSize = this.lastLuminalIds.length
    const yinRatio = 1 - (recentAvgLuminalSize / highPotCount)

    // Coverage ratio: what fraction of sectors-with-engrams have been visited?
    const visitedSectors = this.attractor.getSectorCoverage(sectorCount)
    const sectorsWithEngrams = this.sectorDensityCache.size
    const coverageRatio = visitedSectors.size / Math.max(1, sectorsWithEngrams)

    // Weighted blend: 0.6 weight on coverage (structural Yin) over recency (dynamic Yin)
    const harmony = 0.4 * yinRatio + 0.6 * coverageRatio

    this.lastHarmony = Math.max(0, Math.min(1, harmony))
    return this.lastHarmony
  }

  /** Return the last computed harmony value (doesn't recompute). */
  getHarmony(): number {
    return this.lastHarmony
  }

  /**
   * Build shadow context string for the DMN observer.
   * Identifies blind spots — sectors with high-pot engrams that the attractor
   * hasn't visited — and includes the current harmony metric.
   * Returns null if no shadow observations to report.
   */
  buildShadowContext(): string | null {
    const sectorCount = DEFAULT_SECTOR_COUNT
    const visitedSectors = this.attractor.getSectorCoverage(sectorCount)
    const density = this.sectorDensityCache.size > 0
      ? this.sectorDensityCache
      : this.computeSectorDensity(sectorCount)
    // Harmony was already computed during retrieve — use cached value
    const harmony = this.lastHarmony

    // Find sectors with engrams but no visits (blind spots)
    const blindSpots: Array<{ sector: number; thetaStart: number; thetaEnd: number; count: number }> = []

    for (const [sector, count] of density) {
      if (!visitedSectors.has(sector)) {
        blindSpots.push({
          sector,
          thetaStart: sector * SECTOR_SIZE,
          thetaEnd: (sector + 1) * SECTOR_SIZE,
          count,
        })
      }
    }

    if (blindSpots.length === 0 && harmony >= 0.3 && harmony <= 0.7) {
      return null // Everything is balanced, nothing to report
    }

    const parts: string[] = ['<shadow>']

    if (blindSpots.length > 0) {
      const topBlind = blindSpots.sort((a, b) => b.count - a.count).slice(0, 3)
      const sectorDesc = topBlind
        .map(b => `θ=${(b.thetaStart * 180 / Math.PI).toFixed(0)}°–${(b.thetaEnd * 180 / Math.PI).toFixed(0)}° (${b.count} engrams)`)
        .join(', ')
      parts.push(`Blind spots — sectors with high-pot engrams never visited: ${sectorDesc}`)
    }

    parts.push(`Harmony: ${harmony.toFixed(2)} (${harmony < 0.3 ? 'Yang-dominated' : harmony > 0.7 ? 'Yin-dominated' : 'balanced'})`)
    parts.push('</shadow>')

    return parts.join('\n')
  }

  /**
   * Global Workspace Broadcast (Phase 1): signal the entire field about what
   * the luminal set is holding. Computes the spatial centroid of luminal
   * engrams and primes nuclei that are spatially close to it.
   *
   * Fire-and-forget — never blocks the retrieve return path.
   * Priming is in-memory only, exponential decay with 30s half-life.
   *
   * @param luminalIds IDs of engrams in the luminal set (post-rerank, post-filter)
   * @returns BroadcastResult or null if the luminal set is empty
   */
  private broadcastGlobalWorkspace(luminalIds: string[]): import('./types.js').BroadcastResult | null {
    const start = Date.now()

    // No luminal engrams -> nothing to broadcast
    if (luminalIds.length === 0) return null

    // Get luminal engram positions
    const luminalEngrams = this.cortex.getEngrams(luminalIds)
    const positioned = Array.from(luminalEngrams.values())
      .filter(e => e.x !== 0 || e.y !== 0)

    if (positioned.length === 0) return null

    // Compute broadcast centroid (mean x, mean y)
    const broadcastX = positioned.reduce((s, e) => s + e.x, 0) / positioned.length
    const broadcastY = positioned.reduce((s, e) => s + e.y, 0) / positioned.length

    // Expire any primed nuclei whose time has passed
    const now = Date.now()
    for (const [id, prime] of this.primedNuclei) {
      if (now >= prime.expiresAt) {
        this.primedNuclei.delete(id)
      }
    }

    // Compute resonance for every nucleus
    const allNuclei = this.cortex.listNuclei()
    let nucleiPrimed = 0
    let nucleiIgnored = 0

    for (const nucleus of allNuclei) {
      // Spatial distance from broadcast centroid to nucleus centroid
      const dx = broadcastX - nucleus.centroidX
      const dy = broadcastY - nucleus.centroidY
      const distance = Math.sqrt(dx * dx + dy * dy)

      // Resonance: inverse distance, clamped to [0, 1]
      // Nuclei at distance 0 get resonance 1.0; at distance 1.0 get 0.5
      const resonance = 1 / (1 + distance)

      if (resonance >= this.broadcastResonanceThreshold) {
        // Prime this nucleus
        this.primedNuclei.set(nucleus.id, {
          nucleusId: nucleus.id,
          resonance,
          expiresAt: now + 30_000, // 30s half-life
        })
        nucleiPrimed++
      } else {
        nucleiIgnored++
      }
    }

    const durationMs = Date.now() - start

    this.logger.info('Global workspace broadcast complete', {
      luminalSize: luminalIds.length,
      positioned: positioned.length,
      broadcastX: Number(broadcastX.toFixed(4)),
      broadcastY: Number(broadcastY.toFixed(4)),
      nucleiPrimed,
      nucleiIgnored,
      totalNuclei: allNuclei.length,
      durationMs,
    })

    return { nucleiPrimed, nucleiIgnored, broadcastX, broadcastY, durationMs }
  }

  /**
   * Get the current spark point modulation for an engram.
   * If the engram belongs to a primed nucleus, its spark point is lowered
   * (making it easier to ignite). Returns 1.0 (no modulation) if not primed.
   *
   * Called from KindlingEngine during ignite.
   */
  getBroadcastSparkModulation(engramId: string): number {
    const engram = this.cortex.getEngram(engramId)
    if (!engram || !engram.clusterId) return 1.0

    const prime = this.primedNuclei.get(engram.clusterId)
    if (!prime || Date.now() >= prime.expiresAt) return 1.0

    // Modulation: 1.0 (no change) -> MIN_SPARK_MODULATION (max lowering)
    // Higher resonance = stronger lowering
    const MIN_SPARK_MODULATION = 0.1
    return 1.0 - (1.0 - MIN_SPARK_MODULATION) * prime.resonance
  }

  /** Return currently primed nuclei (for admin API observability). */
  getPrimedNuclei(): Array<{ nucleusId: string; resonance: number; expiresAt: number }> {
    const now = Date.now()
    return [...this.primedNuclei.values()]
      .filter(p => now < p.expiresAt)
      .map(p => ({ nucleusId: p.nucleusId, resonance: p.resonance, expiresAt: p.expiresAt }))
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

  /** List engrams by node type, ordered by potentiation descending. */
  listByType(nodeType: string, limit = 50): Engram[] {
    return this.cortex.listEngrams(limit, nodeType)
  }

  /** List top engrams by potentiation across all types. */
  listPopular(limit = 20): Engram[] {
    return this.cortex.listEngrams(limit)
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

      // Release large allocations so GC can reclaim them before we return.
      // V8 collects these on scope exit; explicit nulling speeds reclamation
      // of the multi-GB SharedArrayBuffer used by the UMAP worker.
      void (buffer)
      void (ids)

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

      // Filaments deprecated — no longer embedding sentence fragments
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
   * Bulk backfill all engrams missing embeddings using batch embedding and
   * bulk SQL updates. After completion, triggers a full reprojection.
   * Returns the total number of engrams embedded and elapsed time.
   */
  async backfillAllEmbeddings(): Promise<{ embedded: number; reprojected: number; durationMs: number }> {
    const startMs = Date.now()
    const embSvc = getEmbeddingService(this.logger)
    if (!embSvc.available) {
      throw new Error('Embedding service not available')
    }

    let totalEmbedded = 0
    const BATCH_SIZE = 1000

    // eslint-disable-next-line no-constant-condition
    while (true) {
      const missing = this.cortex.getEngramsWithoutEmbedding(BATCH_SIZE)
      if (missing.length === 0) break

      const texts = missing.map(e => e.content)
      const vecs = await embSvc.embedBatch(texts, 'document')

      const updates: Array<{ id: string; embedding: Float32Array }> = []
      for (let i = 0; i < missing.length; i++) {
        const vec = vecs[i]
        if (vec) {
          updates.push({ id: missing[i].id, embedding: new Float32Array(vec) })
        }
      }

      if (updates.length > 0) {
        this.cortex.bulkUpdateEmbeddings(updates)
        totalEmbedded += updates.length
      }

      this.logger.info('Backfill batch complete', {
        batchSize: missing.length,
        embedded: updates.length,
        totalSoFar: totalEmbedded,
        remaining: this.cortex.countMissingEmbeddings(),
      })

      // Yield to event loop between batches
      if (missing.length === BATCH_SIZE) {
        await new Promise<void>(resolve => setImmediate(resolve))
      }
    }

    // Full reprojection after all embeddings are in place
    let reprojected = 0
    if (totalEmbedded > 0) {
      reprojected = await this.reprojectAllAsync()
    }

    const durationMs = Date.now() - startMs
    this.logger.info('Backfill all complete', {
      embedded: totalEmbedded,
      reprojected,
      durationMs,
    })

    return { embedded: totalEmbedded, reprojected, durationMs }
  }

  /**
   * Batch classify all engrams missing semanticType labels.
   * Embeds content, runs prototype-set classification against SIGNAL_TYPE_PHRASES,
   * EPISTEMIC_SHIFT_PHRASES, and WORK_UNIT_ANNOTATION_PHRASES, and writes
   * labels to each engram's metadata. After classification, runs the full
   * consolidation cycle so potentiation, drift, and dreaming incorporate labels.
   */
  async classifyAll(limit = 100): Promise<{ classified: number; remaining: number; durationMs: number }> {
    const startMs = Date.now()
    const embSvc = getEmbeddingService(this.logger)
    if (!embSvc.available) {
      throw new Error('Embedding service not available')
    }

    // Ensure prototype centroids are cached for fast classification
    const cache1 = await this.ensurePhraseEmbeddingsForSet(SIGNAL_TYPE_PHRASES)
    const cache2 = await this.ensurePhraseEmbeddingsForSet(EPISTEMIC_SHIFT_PHRASES)
    const cache3 = await this.ensurePhraseEmbeddingsForSet(WORK_UNIT_ANNOTATION_PHRASES)
    if (!cache1 || !cache2 || !cache3) throw new Error('Failed to cache prototype centroids')

    // Collect conversation engrams missing classification labels
    const unclassified = this.cortex.getUnclassifiedConversationEngrams(limit)
    this.logger.info('ClassifyAll: query result', { found: unclassified.length, limit })
    if (unclassified.length === 0) {
      this.logger.info('ClassifyAll: no unclassified conversation engrams')
      return { classified: 0, remaining: 0, durationMs: Date.now() - startMs }
    }

    this.logger.info('ClassifyAll: classifying engrams', { batchSize: unclassified.length })

    let classified = 0
    const BATCH_SIZE = 100

    for (let offset = 0; offset < unclassified.length; offset += BATCH_SIZE) {
      const batch = unclassified.slice(offset, offset + BATCH_SIZE)
      const texts = batch.map(e => e.content.slice(0, 500))

      const vecs = await embSvc.embedBatch(texts, 'document')
      if (!vecs) {
        this.logger.warn('ClassifyAll: embedBatch returned null/empty')
        continue
      }
      const nullCount = vecs.filter(v => !v).length
      if (nullCount > 0) this.logger.warn('ClassifyAll: null embeddings in batch', { nullCount, batchSize: vecs.length })

      for (let i = 0; i < batch.length; i++) {
        const vec = vecs[i]
        if (!vec) continue

        const embedding = new Float32Array(vec)
        const sigType = classifyWithPhrases(batch[i].content, SIGNAL_TYPE_PHRASES, cache1, embedding, cosineSimilarity, 0.15)
        const epiShift = classifyWithPhrases(batch[i].content, EPISTEMIC_SHIFT_PHRASES, cache2, embedding, cosineSimilarity, 0.15)
        const workType = classifyWithPhrases(batch[i].content, WORK_UNIT_ANNOTATION_PHRASES, cache3, embedding, cosineSimilarity, 0.15)

        const labels: Record<string, unknown> = {}
        if (sigType.label) labels.semanticType = sigType.label
        if (epiShift.label) labels.epistemicShift = epiShift.label
        if (workType.label) labels.workType = workType.label

        // Only persist if at least one label matched. Otherwise the engram
        // stays in the unclassified pool for future runs with improved models.
        if (Object.keys(labels).length > 0) {
          labels.classifiedAt = new Date().toISOString()
          // Merge with existing metadata (already in memory from getAllEngrams)
          const eg = batch[i]
          this.cortex.updateEngram(eg.id, {
            metadata: { ...(eg.metadata ?? {}), ...labels },
          })
          classified++
        }
      }

      await new Promise<void>(resolve => setImmediate(resolve))
    }

    const durationMs = Date.now() - startMs
    this.logger.info('ClassifyAll complete', { classified, durationMs })
    return { classified, remaining: 0, durationMs }
  }

  /**
   * Generate 'supports' synapses between engrams that share the same semanticType
   * and have similar content embeddings (cosine similarity > 0.60).
   * Only pairs not already connected by a 'supports' synapse are linked.
   */
  async generateTypeSynapses(): Promise<{ edgesCreated: number; pairsScanned: number; durationMs: number }> {
    const startMs = Date.now()

    // Group classified engrams by semanticType
    const all = this.cortex.getAllEngrams()
    const typeGroups = new Map<string, Engram[]>()

    for (const e of all) {
      const st = (e.metadata?.semanticType as string) ?? ''
      if (!st) continue
      const group = typeGroups.get(st) ?? []
      group.push(e)
      typeGroups.set(st, group)
    }

    if (typeGroups.size === 0) {
      this.logger.info('generateTypeSynapses: no classified engrams')
      return { edgesCreated: 0, pairsScanned: 0, durationMs: Date.now() - startMs }
    }

    let edgesCreated = 0
    let pairsScanned = 0
    const SIMILARITY_THRESHOLD = 0.60
    const MAX_PAIRS_PER_TYPE = 5000  // cap per group to bound runtime

    for (const [type, group] of typeGroups) {
      if (group.length < 2) continue

      // Limit pairs to avoid O(n²) explosion
      const capped = group.slice(0, Math.min(group.length, 200))
      const pairLimit = Math.min(capped.length * capped.length / 2, MAX_PAIRS_PER_TYPE)
      let typeEdges = 0

      for (let i = 0; i < capped.length && typeEdges < pairLimit; i++) {
        for (let j = i + 1; j < capped.length && typeEdges < pairLimit; j++) {
          const a = capped[i]
          const b = capped[j]
          pairsScanned++

          // Skip if synapse already exists in either direction
          if (this.cortex.getSynapse(a.id, b.id, 'supports') ||
              this.cortex.getSynapse(b.id, a.id, 'supports')) {
            continue
          }

          // Load embeddings for similarity comparison
          const aEngram = this.cortex.getEngram(a.id)
          const bEngram = this.cortex.getEngram(b.id)
          if (!aEngram || !bEngram) continue
          const aEmb = aEngram.embedding
          const bEmb = bEngram.embedding
          if (!aEmb || !bEmb) continue

          const sim = cosineSimilarity(aEmb, bEmb)
          if (sim >= SIMILARITY_THRESHOLD) {
            this.cortex.createSynapse({
              sourceId: a.id,
              targetId: b.id,
              edgeType: 'supports',
              weight: Math.round(sim * 100) / 100,
            })
            edgesCreated++
            typeEdges++
          }
        }
      }
    }

    const durationMs = Date.now() - startMs
    this.logger.info('generateTypeSynapses complete', { edgesCreated, pairsScanned, groups: typeGroups.size, durationMs })
    return { edgesCreated, pairsScanned, durationMs }
  }

  /**
   * Batch temporal re-linking + metadata enrichment for engrams created outside
   * the Thalamus write path (migration, archive ingestion). Groups by sessionId,
   * assigns messageIndex, infers slotType from content/tags, creates
   * temporal_neighbor synapses between consecutive engrams, and classifies
   * unlabeled entries via prototype embeddings.
   */
  async thalamusBackfill(): Promise<{
    sessionsProcessed: number
    engramsLabeled: number
    synapsesCreated: number
    engramsClassified: number
    durationMs: number
    errors: string[]
  }> {
    const startMs = Date.now()
    const errors: string[] = []

    // 1. Lean load — only engrams with sessionId metadata, skip embedding blobs
    let rows: Array<Record<string, unknown>>
    try {
      rows = this.db.prepare(`
        SELECT id, content, metadata, t, tags, node_type, provenance
        FROM engrams
        WHERE json_extract(metadata, '$.sessionId') IS NOT NULL
      `).all() as Array<Record<string, unknown>>
    } catch (err) {
      this.logger.error('thalamusBackfill: failed to query engrams', { error: String(err) })
      return { sessionsProcessed: 0, engramsLabeled: 0, synapsesCreated: 0, engramsClassified: 0, durationMs: Date.now() - startMs, errors: [String(err)] }
    }

    this.logger.info('thalamusBackfill: loaded engrams', { rows: rows.length })

    // 2. Group by sessionId
    const sessionGroups = new Map<string, Array<{
      id: string; content: string; metadata: Record<string, unknown>;
      t: number; tags: string[]; nodeType: string; provenance: string | null
    }>>()

    for (const row of rows) {
      let meta: Record<string, unknown>
      try { meta = JSON.parse(row.metadata as string || '{}') as Record<string, unknown> } catch { meta = {} }
      const sessionId = meta.sessionId as string | undefined
      if (!sessionId) continue

      let tags: string[] = []
      try { tags = JSON.parse(row.tags as string || '[]') } catch {}

      const group = sessionGroups.get(sessionId) ?? []
      group.push({
        id: row.id as string,
        content: row.content as string,
        metadata: meta,
        t: row.t as number,
        tags,
        nodeType: row.node_type as string,
        provenance: row.provenance as string | null,
      })
      sessionGroups.set(sessionId, group)
    }

    this.logger.info('thalamusBackfill: grouped into sessions', { uniqueSessions: sessionGroups.size })

    // 3. Pre-warm prototype phrase caches
    this.logger.info('thalamusBackfill: caching prototype centroids')
    const cache1 = await this.ensurePhraseEmbeddingsForSet(SIGNAL_TYPE_PHRASES)
    const cache2 = await this.ensurePhraseEmbeddingsForSet(EPISTEMIC_SHIFT_PHRASES)
    const cache3 = await this.ensurePhraseEmbeddingsForSet(WORK_UNIT_ANNOTATION_PHRASES)

    let sessionsProcessed = 0
    let engramsLabeled = 0
    let synapsesCreated = 0
    let engramsClassified = 0
    const embSvc = getEmbeddingService(this.logger)
    const embAvailable = embSvc.available && cache1 && cache2 && cache3

    // Collect unlabeled engrams for batch classification
    const unlabeled: Array<{ id: string; content: string }> = []

    // 4. Process each session
    for (const [sessionId, engrams] of sessionGroups) {
      if (engrams.length < 1) continue

      // Sort by timestamp (ascending)
      engrams.sort((a, b) => a.t - b.t)

      let sessionChanges = 0
      let sessionSynapses = 0

      for (let i = 0; i < engrams.length; i++) {
        const eg = engrams[i]
        const mergedMeta: Record<string, unknown> = { ...eg.metadata }

        // Skip engrams already from the Thalamus pipeline
        if (eg.provenance === 'thalamus') continue

        let changed = false

        // Assign messageIndex if missing
        if (mergedMeta.messageIndex === undefined) {
          mergedMeta.messageIndex = i
          changed = true
        }

        // Infer slotType if missing
        if (!mergedMeta.slotType) {
          const upper = eg.content.toUpperCase().slice(0, 20)
          if (eg.tags.includes('user_message') || eg.tags.includes('user') || upper.startsWith('USER')) mergedMeta.slotType = 'user_message'
          else if (eg.tags.includes('assistant_message') || eg.tags.includes('assistant') || upper.startsWith('ASSISTANT')) mergedMeta.slotType = 'assistant_message'
          else if (eg.tags.includes('system_message') || eg.tags.includes('system') || upper.startsWith('SYSTEM')) mergedMeta.slotType = 'system_message'
          else mergedMeta.slotType = 'unknown'
          changed = true
        }

        // Tag backfill provenance in metadata
        if (eg.provenance !== 'thalamus' && eg.provenance !== 'thalamus_backfill') {
          mergedMeta.backfilledAt = new Date().toISOString()
          mergedMeta._provenance = 'thalamus_backfill'
          changed = true
        }

        if (changed) {
          this.cortex.updateEngram(eg.id, { metadata: mergedMeta })
          engramsLabeled++
          sessionChanges++
        }

        // Collect for classification if unlabeled
        if (embAvailable && !mergedMeta.semanticType && eg.content.length >= 10) {
          unlabeled.push({ id: eg.id, content: eg.content.slice(0, 500) })
        }
      }

      // Create temporal_neighbor synapses between consecutive engrams
      for (let i = 0; i < engrams.length - 1; i++) {
        const a = engrams[i]
        const b = engrams[i + 1]
        if (!this.cortex.getSynapse(a.id, b.id, 'temporal_neighbor')) {
          try {
            this.cortex.createSynapse({
              sourceId: a.id,
              targetId: b.id,
              edgeType: 'temporal_neighbor',
              weight: 1.0,
            })
            synapsesCreated++
            sessionSynapses++
          } catch { /* synapse may have been created in a race */ }
        }
      }

      if (sessionChanges > 0 || sessionSynapses > 0) {
        sessionsProcessed++
      }

      // Yield to event loop
      if (sessionsProcessed > 0 && sessionsProcessed % 200 === 0) {
        await new Promise<void>(resolve => setImmediate(resolve))
      }
    }

    // 5. Batch classify unlabeled engrams
    if (embAvailable && unlabeled.length > 0) {
      this.logger.info('thalamusBackfill: classifying unlabeled engrams', { count: unlabeled.length })
      const CLASSIFY_BATCH = 50
      for (let offset = 0; offset < unlabeled.length; offset += CLASSIFY_BATCH) {
        const batch = unlabeled.slice(offset, offset + CLASSIFY_BATCH)
        const texts = batch.map(e => e.content.slice(0, 500))
        const vecs = await embSvc.embedBatch(texts, 'document')
        if (!vecs) continue

        for (let i = 0; i < batch.length; i++) {
          const vec = vecs[i]
          if (!vec) continue
          const embedding = new Float32Array(vec)

          const sigType = classifyWithPhrases(batch[i].content, SIGNAL_TYPE_PHRASES, cache1!, embedding, cosineSimilarity, 0.30)
          const epiShift = classifyWithPhrases(batch[i].content, EPISTEMIC_SHIFT_PHRASES, cache2!, embedding, cosineSimilarity, 0.30)
          const workType = classifyWithPhrases(batch[i].content, WORK_UNIT_ANNOTATION_PHRASES, cache3!, embedding, cosineSimilarity, 0.30)

          const labels: Record<string, unknown> = { classifiedAt: new Date().toISOString() }
          if (sigType.label) labels.semanticType = sigType.label
          if (epiShift.label) labels.epistemicShift = epiShift.label
          if (workType.label) labels.workType = workType.label

          if (labels.semanticType || labels.epistemicShift || labels.workType) {
            const existing = this.cortex.getEngram(batch[i].id)
            if (existing) {
              this.cortex.updateEngram(batch[i].id, {
                metadata: { ...(existing.metadata ?? {}), ...labels },
              })
              engramsClassified++
            }
          }
        }

        await new Promise<void>(resolve => setImmediate(resolve))
      }
    }

    const durationMs = Date.now() - startMs
    this.logger.info('thalamusBackfill complete', {
      sessionsProcessed, engramsLabeled, synapsesCreated, engramsClassified, durationMs,
    })
    return { sessionsProcessed, engramsLabeled, synapsesCreated, engramsClassified, durationMs, errors }
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
          // Telemetry signal — should fade fast and not flood active-cortex injection.
          // Previously clamped to 0.7 which kept it sticky across many turns.
          salience: 0.05,
          tags: ['mnemic-retrieval', 'telemetry'],
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
  getAnnStats(): { engram: { vectorCount: number; needsRebuild: boolean; maxElements: number; dimension: number } | null } {
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

      // Mirror feedback into Lightning Indexer training. Same signal,
      // different consumer: the indexer learns to rank engrams the way
      // helpful/unhelpful feedback says they should be ranked.
      const indexerTriples = this.feedbackToIndexerTriples(feedback)
      if (indexerTriples.length > 0) {
        const persisted = this.cortex.recordIndexerTrainingRequests(indexerTriples)
        this.logger.debug('Indexer training triples persisted from feedback', {
          retrievalId: this.lastRetrievalId,
          tripleCount: indexerTriples.length,
          persisted,
        })
      }

      return true
    } catch (err) {
      this.logger.warn('Failed to store gradient request', { error: err })
      return false
    }
  }

  /**
   * Convert helpful/unhelpful feedback into Lightning Indexer training triples,
   * keyed by the most recent retrieval. Engrams in feedback that didn't appear
   * in the last retrieval's candidate set are dropped (no event to attach to).
   */
  private feedbackToIndexerTriples(feedback: Record<string, boolean>): RetrievalLabelTriple[] {
    if (!this.lastRetrievalId || this.lastRetrievalCandidates.length === 0) return []

    const candidatePosition = new Map<string, number>()
    for (let i = 0; i < this.lastRetrievalCandidates.length; i++) {
      candidatePosition.set(this.lastRetrievalCandidates[i]!, i)
    }

    const observedAt = new Date().toISOString()
    const triples: RetrievalLabelTriple[] = []
    for (const [engramId, helpful] of Object.entries(feedback)) {
      const idx = candidatePosition.get(engramId)
      if (idx === undefined) continue
      triples.push({
        retrievalId: this.lastRetrievalId,
        candidateId: engramId,
        label: helpful ? 'used' : 'ignored',
        weight: 1.0,
        evidence: [{
          signal: 'enrich_feedback' as RetrievalLabelTriple['evidence'][number]['signal'],
          details: { helpful, position: idx },
          observedAt,
        }],
        indexerScore: this.lastRetrievalIndexerScores?.[idx] ?? undefined,
        rerankerScore: this.lastRetrievalRerankerScores?.[idx] ?? undefined,
      })
    }
    return triples
  }

  /**
   * Persist Lightning Indexer training requests produced by Reverie's labeler.
   * Returns the number of rows written.
   */
  recordIndexerTrainingRequests(triples: RetrievalLabelTriple[]): number {
    if (triples.length === 0) return 0
    try {
      return this.cortex.recordIndexerTrainingRequests(triples)
    } catch (err) {
      this.logger.warn('Failed to record indexer training requests', { error: String(err) })
      return 0
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
    // Refresh sector density before consolidation — the topology may have
    // changed since the last scan (new engrams, potentiation shifts).
    try {
      this.computeSectorDensity()
    } catch { /* never block consolidation for density scan failures */ }

    return this.consolidationEngine.consolidate(options)
  }

  /**
   * Bridge entry point for the legacy detector. Forwards promotion
   * candidates to the mnemic-side consolidation engine which creates
   * pattern engrams and supersedes synapses.
   */
  consolidatePromotionCandidates(
    candidates: ReadonlyArray<{ key: string; from: string; to: string }>,
  ): number {
    return this.consolidationEngine.consolidatePromotionCandidates(candidates)
  }

  // contributing:ignore — Deprecated filament methods removed. Keep stubs for API compat.

  getFilaments(_engramId?: string): Array<{ id: number; engramId: string; content: string; createdAt: string }> {
    this.logger.debug('getFilaments: filaments removed')
    return []
  }

  async embedFilaments(): Promise<number> {
    return 0
  }

  async backfillFilaments(_batchSize?: number): Promise<{ segmented: number; embedded: number; linked: number }> {
    return { segmented: 0, embedded: 0, linked: 0 }
  }

  getChains(_engramIds?: string[]): Array<{ filaments: Array<{ id: number; engramId: string; content: string; createdAt: string }>; edgeTypes: string[]; length: number }> {
    return []
  }

  getCrystallization(): Array<{ filamentId: number; content: string; confirmCount: number; contradictCount: number; status: string }> {
    return []
  }

  getExpertiseMetrics(): Array<{ nucleusId: string; label: string; filamentDensity: number; synapseDensity: number; chainDepth: number; status: string }> {
    return []
  }

  getStaleDependents(): number[] {
    return []
  }

  renderContext(
    query: string,
    options: KindlingOptions & { tokenBudget?: number },
  ): { entries: Array<{ engramId: string; zoom: string; rendered: string; tokenEstimate: number }>; totalTokens: number } {
    const luminal = this.kindle(null, query, options)
    return {
      entries: luminal.engrams.map((e) => ({
        engramId: e.engram.id,
        zoom: 'full' as const,
        tokenEstimate: Math.ceil(e.engram.content.length / 4),
        rendered: e.engram.content.slice(0, 500),
      })),
      totalTokens: luminal.engrams.reduce((s, e) => s + Math.ceil(e.engram.content.length / 4), 0),
    }
  }

  buildDelegationContext(
    query: string,
    options: KindlingOptions,
  ): { renderedText: string } {
    const luminal = this.kindle(null, query, options)
    const renderedText = luminal.engrams.map(e => e.engram.content).join('\n\n')
    return { renderedText }
  }

  setLlmProvider(_provider: IProvider): void {
    this.logger.debug('setLlmProvider: filament analysis removed')
  }

  getFilamentCortex(): null {
    return null
  }

  /**
   * Get the underlying Cortex for direct operations.
   * Prefer using MnemicField methods; use this for advanced/batch operations.
   */
  getCortex(): Cortex {
    return this.cortex
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

  /**
   * Set the dream engine for consolidation-time discovery of hidden connections.
   * The dream engine walks engrams through the vindex to find feature overlap.
   */
  setDreamEngine(engine: DreamEngine): void {
    this.dreamEngine = engine
    this.consolidationEngine = new ConsolidationEngine(
      this.cortex,
      this.logger,
      this.gradientEngine,
      this.dreamEngine,
    )
    this.logger.info('Dream engine connected to consolidation pipeline')
  }

  /**
   * Default radial distance for engram types when no position is specified.
   * Lower = closer to center = higher attentional priority.
   * Returns undefined to let store() apply the standard periphery fallback.
   */
  private static getDefaultRadial(nodeType: string): number | undefined {
    if (nodeType === 'pineal_facet') return 0
    if (nodeType === 'fact' || nodeType === 'decision') return 0.15 + Math.random() * 0.1
    if (nodeType === 'insight' || nodeType === 'pattern') return 0.20 + Math.random() * 0.1
    if (nodeType === 'expert_summary' || nodeType === 'abstraction') return 0.12 + Math.random() * 0.1
    if (nodeType === 'goal') return 0.18 + Math.random() * 0.1
    if (nodeType === 'tool' || nodeType === 'tool_invocation') return 0.55 + Math.random() * 0.1
    if (nodeType === 'file' || nodeType === 'file_version') return 0.50 + Math.random() * 0.1
    if (nodeType === 'message' || nodeType === 'episode') return 0.80 + Math.random() * 0.1
    if (nodeType === 'file_read') return 0.90 + Math.random() * 0.05
    if (nodeType === 'bridge') return 0.75 + Math.random() * 0.1
    return undefined
  }

  storeForSession(input: EngramCreate & { sessionId?: string }): Engram {
    const sessionId = input.sessionId
    // Auto-assign radial position from nodeType when no position specified
    let resolved = input
    if (input.x === undefined && input.y === undefined
        && input.r === undefined && input.theta === undefined) {
      const r = MnemicField.getDefaultRadial(input.nodeType)
      if (r !== undefined) {
        resolved = { ...input, r }
      }
    }
    if (sessionId) {
      const metadata = { ...(resolved.metadata ?? {}), sessionId }
      const { sessionId: _sid, ...rest } = resolved
      const result = this.store({ ...rest, metadata })
      try {
        this.cortex.setEngramSessionId(result.id, sessionId)
      } catch {
        // Non-fatal — sessionId is in metadata
      }
      return result
    }
    return this.store(resolved)
  }

  findExpertEngrams(query: import('./types.js').ExpertQuery = {}): Engram[] {
    const all = this.cortex.listEngrams(query.limit ?? 500, 'expert_summary')
    return all.filter(e => {
      const m = e.metadata ?? {}
      if (query.expertKind && (m as any).expertKind !== query.expertKind) return false
      if (query.expertDomain && (m as any).expertDomain !== query.expertDomain) return false
      if (query.expertPinned !== undefined && (m as any).expertPinned !== query.expertPinned) return false
      if (query.minConviction !== undefined && ((m as any).expertConviction ?? 0) < query.minConviction) return false
      if (query.expertScope !== undefined) {
        const scope = (m as any).expertScope ?? null
        if (query.expertScope !== scope && scope !== null) return false
      }
      return true
    }).sort((a, b) => ((b.metadata as any)?.expertConviction ?? 0) - ((a.metadata as any)?.expertConviction ?? 0))
  }

  getTrace(options: import('./types.js').TraceOptions = {}): import('./types.js').TraceEvent[] {
    const limit = options.limit ?? 1000
    let engrams: import('./types.js').Engram[]

    if (options.sessionIds?.length === 1) {
      engrams = this.cortex.getEngramsBySessionId(options.sessionIds[0], limit)
    } else {
      const all = this.cortex.listEngrams(options.limit ?? 10000)
      engrams = all.filter(e => !options.sessionIds?.length || (options.sessionIds as string[]).includes((e.metadata as any)?.sessionId ?? ''))
    }

    if (options.expertId) {
      engrams = engrams.filter(e => (e.metadata as any)?.expertId === options.expertId)
    }
    if (options.from) {
      const from = new Date(options.from).getTime()
      engrams = engrams.filter(e => e.t >= from)
    }
    if (options.to) {
      const to = new Date(options.to).getTime()
      engrams = engrams.filter(e => e.t <= to)
    }

    engrams.sort((a, b) => a.t - b.t)
    const slice = engrams.slice(0, limit)

    const events: import('./types.js').TraceEvent[] = []
    for (const engram of slice) {
      const sid = (engram.metadata as any)?.sessionId as string | undefined
      if (!sid) continue
      events.push({
        sessionId: sid,
        timestamp: engram.createdAt,
        engram,
        edges: [],
        expertInjections: (engram.metadata as any)?.expertInjections as string[] | undefined,
      })
    }
    return events
  }

  reinforceExpert(expertId: string): Engram | null {
    const all = this.cortex.listEngrams(1000, 'expert_summary')
    const target = all.find(e => (e.metadata as any)?.expertId === expertId)
    if (!target) return null
    const m = target.metadata as any
    const conviction = (m.expertConviction ?? 0.2) as number
    const increment = 0.02 * (1 - conviction)
    const newConviction = Math.min(1, conviction + increment)
    const updated = this.cortex.updateEngram(target.id, {
      metadata: {
        ...m,
        expertConviction: newConviction,
        expertLastReinforced: new Date().toISOString(),
        expertReinforcements: (m.expertReinforcements ?? 0) + 1,
      },
    })
    if (updated) {
      this.logger.debug('Expert reinforced', {
        expertId,
        conviction: `${conviction.toFixed(3)} → ${newConviction.toFixed(3)}`,
      })
    }
    return updated
  }

  evolveExpert(expertId: string, newContent: string, input?: Partial<import('./types.js').EngramCreate>): Engram | null {
    const all = this.cortex.listEngrams(1000, 'expert_summary')
    const target = all.find(e => (e.metadata as any)?.expertId === expertId)
    if (!target) return null
    const oldActive = (target.metadata as any)?.active
    if (oldActive === false) return null
    const oldMeta = target.metadata as any
    const newMeta = {
      ...oldMeta,
      expertEvolvedFrom: target.id,
      expertVersion: (oldMeta.expertVersion ?? 1) + 1,
      expertConviction: 0.2,
      expertLastReinforced: new Date().toISOString(),
      expertReinforcements: 0,
      active: true,
    }
    const updated = this.cortex.updateEngram(target.id, {
      metadata: { ...oldMeta, active: false },
    })
    if (!updated) return null
    const evolved = this.store({
      ...(input ?? {}),
      content: newContent,
      nodeType: 'expert_summary',
      provenance: input?.provenance ?? 'thalamus.evolve',
      metadata: newMeta,
    })
    this.logger.info('Expert evolved', {
      fromId: target.id,
      toId: evolved.id,
      version: newMeta.expertVersion,
    })
    return evolved
  }

  checkExpertLifecycle(): { dormant: string[]; archived: string[]; hot: string[] } {
    const all = this.cortex.listEngrams(10000, 'expert_summary')
    const now = new Date()
    const dormant: string[] = []
    const archived: string[] = []
    const hot: string[] = []
    for (const e of all) {
      const m = e.metadata as any
      if (!m?.expertId) continue
      const lastMsg = m.expertLastReinforced ? new Date(m.expertLastReinforced) : null
      const msgCount = m.expertSourceIds?.length ?? 0
      if (lastMsg) {
        const daysOld = (now.getTime() - lastMsg.getTime()) / 86400000
        if (daysOld > 90 && msgCount < 5) archived.push(m.expertId)
        else if (daysOld > 30) dormant.push(m.expertId)
      }
      if ((m.expertReinforcements ?? 0) > 50) hot.push(m.expertId)
    }
    return { dormant, archived, hot }
  }

  private async _ensurePhraseEmbeddings(): Promise<Map<string, Float32Array> | null> {
    if (this._phraseEmbeddings) return this._phraseEmbeddings

    const embSvc = getEmbeddingService(this.logger)
    if (!embSvc.available) return null

    const allPhrases: string[] = []
    const phraseIndex: { edgeType: string; indices: number[] }[] = []

    for (const edgeType of Object.keys(RELATIONAL_PHRASES)) {
      const start = allPhrases.length
      const phrases = RELATIONAL_PHRASES[edgeType]
      let count = 0
      for (const p of phrases) {
        allPhrases.push(p)
        count++
      }
      phraseIndex.push({ edgeType, indices: Array.from({ length: count }, (_, i) => start + i) })
    }

    const batchSize = 10
    const allEmbeddings: Float32Array[] = []
    for (let i = 0; i < allPhrases.length; i += batchSize) {
      const batch = allPhrases.slice(i, i + batchSize)
      const results = await Promise.all(batch.map(p => embSvc.embed(p)))
      for (const r of results) {
        if (r) {
          allEmbeddings.push(new Float32Array(r))
        }
      }
    }

    const dim = allEmbeddings[0]?.length ?? 1024
    this._phraseEmbeddings = new Map()

    for (const { edgeType, indices } of phraseIndex) {
      const centroid = new Float32Array(dim)
      let count = 0
      for (const idx of indices) {
        if (idx < allEmbeddings.length) {
          for (let d = 0; d < dim; d++) centroid[d] += allEmbeddings[idx][d]
          count++
        }
      }
      if (count > 0) {
        for (let d = 0; d < dim; d++) centroid[d] /= count
        this._phraseEmbeddings.set(edgeType, centroid)
      }
    }

    return this._phraseEmbeddings
  }

  private outcomeLog: Array<{ expertId: string; outcome: 'positive' | 'negative' | 'missing'; turn: number }> = []
  private outcomeLogCapacity = 500

  recordExpertOutcome(expertId: string, outcome: 'positive' | 'negative' | 'missing'): void {
    this.outcomeLog.push({ expertId, outcome, turn: this.outcomeLog.length })
    if (this.outcomeLog.length > this.outcomeLogCapacity) {
      this.outcomeLog.splice(0, this.outcomeLog.length - this.outcomeLogCapacity)
    }
    if (outcome === 'positive') {
      this.reinforceExpert(expertId)
    }
  }

  adjustPropagationWeights(): Record<string, number> {
    if (this.outcomeLog.length < 10) return {}
    const positiveCount = new Map<string, number>()
    const negativeCount = new Map<string, number>()
    for (const entry of this.outcomeLog) {
      const map = entry.outcome === 'negative' ? negativeCount : positiveCount
      map.set(entry.expertId, (map.get(entry.expertId) ?? 0) + 1)
    }
    const adjustments: Record<string, number> = {}
    for (const [expertId, pos] of positiveCount) {
      const neg = negativeCount.get(expertId) ?? 0
      const total = pos + neg
      if (total >= 5) {
        const rate = pos / total
        adjustments[expertId] = rate
      }
    }
    return adjustments
  }

  async classifyEdgePair(sourceId: string, targetId: string): Promise<import('./types.js').SynapseType | null> {
    const source = this.get(sourceId)
    const target = this.get(targetId)
    if (!source || !target) return null

    const phraseEmbeddings = await this._ensurePhraseEmbeddings()
    if (!phraseEmbeddings) return null

    const embSvc = getEmbeddingService(this.logger)
    if (!embSvc.available) return null

    const combined = `${source.content.slice(0, 200)}\n${target.content.slice(0, 200)}`
    const embedding = await embSvc.embed(combined)
    if (!embedding) return null

    const result = classifyEdge(
      source.content,
      target.content,
      phraseEmbeddings,
      new Float32Array(embedding),
      cosineSimilarity,
      0.35,
    )

    if (result.edgeType) {
      this.cortex.createSynapse({
        sourceId,
        targetId,
        edgeType: result.edgeType,
        weight: result.score,
        metadata: { classifier: 'edge-relators', confidence: result.score },
      })
    }

    return result.edgeType
  }

  async classifyPhrase(
    text: string,
    prototypeSet: PhrasePrototypeSet,
    threshold = 0.35,
  ): Promise<ClassificationResult> {
    const cache = await this.ensurePhraseEmbeddingsForSet(prototypeSet)
    if (!cache) return { label: null, score: 0 }

    const embSvc = getEmbeddingService(this.logger)
    if (!embSvc.available) return { label: null, score: 0 }

    const embedding = await embSvc.embed(text)
    if (!embedding) return { label: null, score: 0 }

    return classifyWithPhrases(
      text,
      prototypeSet,
      cache,
      new Float32Array(embedding),
      cosineSimilarity,
      threshold,
    )
  }

  async ensurePhraseEmbeddingsForSet(
    prototypeSet: PhrasePrototypeSet,
  ): Promise<Map<string, Float32Array> | null> {
    const cacheKey = prototypeSet.labels.join('\0')
    const cached = this._genericPhraseCaches.get(cacheKey)
    if (cached) return cached

    const embSvc = getEmbeddingService(this.logger)
    if (!embSvc.available) return null

    const allPhrases: string[] = []
    const phraseIndex: { label: string; indices: number[] }[] = []

    for (const label of prototypeSet.labels) {
      const phrases = prototypeSet.phrases[label] ?? []
      const start = allPhrases.length
      allPhrases.push(...phrases)
      phraseIndex.push({ label, indices: Array.from({ length: phrases.length }, (_, i) => start + i) })
    }

    if (allPhrases.length === 0) return null

    const batchSize = 10
    const allEmbeddings: Float32Array[] = []
    for (let i = 0; i < allPhrases.length; i += batchSize) {
      const batch = allPhrases.slice(i, i + batchSize)
      const results = await Promise.all(batch.map(p => embSvc.embed(p)))
      for (const r of results) {
        if (r) allEmbeddings.push(new Float32Array(r))
      }
    }

    const dim = allEmbeddings[0]?.length ?? 1024
    const cache = new Map<string, Float32Array>()

    for (const { label, indices } of phraseIndex) {
      const centroid = new Float32Array(dim)
      let count = 0
      for (const idx of indices) {
        if (idx < allEmbeddings.length) {
          for (let d = 0; d < dim; d++) centroid[d] += allEmbeddings[idx][d]
          count++
        }
      }
      if (count > 0) {
        for (let d = 0; d < dim; d++) centroid[d] /= count
        cache.set(`embed:${label}`, centroid)
      }
    }

    this._genericPhraseCaches.set(cacheKey, cache)
    return cache
  }

  close(): void {
    this.cortex.close()
    this.logger.info('Mnemic Field closed')
  }
}
