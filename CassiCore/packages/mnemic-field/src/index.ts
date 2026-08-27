import Database from 'better-sqlite3'
import fs from 'node:fs'
import path from 'node:path'
import { randomUUID } from 'node:crypto'
import { once } from 'node:events'
import { Worker } from 'node:worker_threads'
import { fileURLToPath } from 'node:url'
import type { DreamEngine } from './vendor/core/intelligence/memory-bridge/dream-engine.js'
import type { ILogger } from '@cassicore/foundation'
import { getEmbeddingService } from './vendor/core/intelligence/embeddings/embedding-service.js'
import { getRerankerService } from './vendor/core/intelligence/embeddings/reranker-service.js'
import { getDataDir } from '@cassicore/foundation'
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
import type { AffectState, LightningRetrievalMode, LightningRetrievalEvent, RerankerMode, IndexerTrainingConfig } from './types.js'
import { INDEXER_TRAINING_DEFAULTS } from './types.js'
import { FeatureIndex, type VindexGateKnnFn } from './feature-index.js'
import { LmdbFeatureIndex, type IndexResult } from './feature-index-lmdb.js'
import { EngramQualityScorer, type ForwardProvider } from './engram-quality-scorer.js'
import type { EngramDecomposer } from './engram-decomposer.js'
import { scoreSentencesByOverlap } from './engram-decomposer.js'
import {
  tokenizePosition,
  positionToFieldCoords,
  generateSpatialGrid,
} from './spatial-tokenizer.js'
import type { RetrievalLabelTriple } from './vendor/core/intelligence/reverie/retrieval-labeler-types.js'
import type { LabelerInputCandidate } from './vendor/core/intelligence/reverie/retrieval-labeler-types.js'
import type { CorticalField } from '@cassicore/cortex-pineal-dialectic'
import type { IProvider } from '@cassicore/foundation'
import { LLMReranker, type LLMRerankerConfig } from './llm-reranker.js'
import { LightningIndexer } from './lightning-indexer.js'
import { IndexerTrainer, type RunOnceResult } from './training/indexer-trainer.js'
import { SpatialIndex } from './spatial-index.js'
import { RELATIONAL_PHRASE_EDGE_TYPES, classifyEdge, RELATIONAL_PHRASES, classifyWithPhrases, type PhrasePrototypeSet, type ClassificationResult, EDGE_RELATORS_PHRASE_SET } from './edge-relators.js'
import { SIGNAL_TYPE_PHRASES, EPISTEMIC_SHIFT_PHRASES, WORK_UNIT_ANNOTATION_PHRASES } from '@cassicore/foundation'
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
  PrimedNucleus, BroadcastResult,
} from './types.js'

/**
 * Minimal type for a vindex-based embedding provider.
 * Satisfied by LarqlKnowledgeProvider.gateEmbed() and embedWithPatch().
 */
export type VindexEmbedder = (text: string, options?: {
  layers?: number[]
  featuresPerLayer?: number
  minScore?: number
  /** Feature patches for causal retrieval — boost/dampen specific features. */
  patches?: Array<{ layer: number; featureIndex: number; boost: number }>
  /** Vindex source to use for multi-vindex setups. */
  source?: string
}) => Float32Array | null
import { SPARK_POINT_DEFAULTS, POTENTIATION_DEFAULTS } from './types.js'

const REPROJECTION = {
  cooldownMs: 30 * 60 * 1000,    // 30 min between runs
  maxFailures: 2,                 // block after this many consecutive failures
} as const

/** Floor on broadcast spark point modulation — prevents zero ignition. */
const MIN_SPARK_MODULATION = 0.1

/** Default resonance threshold for nucleus priming during broadcast. */
const BRADCAST_RESONANCE_THRESHOLD = 0.3

/** Structural engram types excluded from user-facing retrieval results. */
const STRUCTURAL_TYPES = new Set([
  'bridge', 'session', 'file', 'source_file', 'file_version', 'file_read',
  'changeset', 'tool_invocation', 'thought_command',
  'replay_segment', 'expert_summary',
])

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
// P7 admin-api: healpix / migrate-memory / annotation sub-module surfaces
export { assignCell, globalCellKey, cellsInSector } from './healpix.js'
export { migrateMemoryOnly, migrateMemoryAndArchives } from './migrate-memory.js'
export { countUnannotated, buildInstruction, findNextUnannotated, findByName, annotateEngram, skipEngram } from './self-model/annotation.js'
export type { AnnotationResponse, AnnotationCandidate } from './self-model/annotation.js'
// P7 admin-api: ingestor/analyzer class surfaces (memory route dynamic imports)
export { VisualIngestor } from './visual-ingestor.js'
export { AttractorExtractor } from './attractor-extractor.js'
export { FieldGenerator } from './field-generator.js'
export { KnowledgeIngestor } from './knowledge/ingestor.js'
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
export { SpatialAttentionMapper } from './spatial-attention.js'
export type { SectorAttentionResult } from './spatial-attention.js'
export {
  tokenizePosition, positionToFieldCoords, generateSpatialGrid,
  positionToTokenId, tokenIdToPosition, normalizePosition, denormalizePosition,
  GRID_SIZE, GRID_SIZE_SQ, GRID_VOLUME,
} from './spatial-tokenizer.js'
export type { SpatialPosition, SpatialPositionWithToken } from './spatial-tokenizer.js'
export { VQSectorPrototypes, cosineSimilarity, cosineDistance } from './vq-prototypes.js'
export { EngramDecomposer, contentDensity, scoreSentencesByOverlap, featuresToKeySet } from './engram-decomposer.js'
export type { SentenceFeature, DensityMetrics, DecomposedContent } from './engram-decomposer.js'
export type { AssignResult } from './vq-prototypes.js'
export type { IngestOptions, IngestResult } from './code-ingestor.js'
export type { ConsolidationResult, ConsolidationOptions } from './consolidation.js'
export { projectTo2D, projectTo2DAsync, projectTo2DFromSAB, projectSingle, buildProjectionState } from './umap.js'
export type { ProjectionResult, ProjectionState, UMAPOptions, UMAPProgressEvent } from './umap.js'
export type {
  Engram, EngramCreate, EngramUpdate,
  MnemicSynapse, SynapseCreate,
  EngramType, SynapseType,
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
  DistinctivenessResult,
  LightningIndexerConfig, LightningIndexerGlobal, LightningCandidate, LightningRanked,
  LightningRetrievalMode, LightningRetrievalEvent,
  IndexerTrainingConfig,
} from './types.js'
export {
  LIGHTNING_INDEXER_DEFAULTS, LIGHTNING_INDEXER_VERSION,
  INDEXER_TRAINING_DEFAULTS,
} from './types.js'
export { LightningIndexer } from './lightning-indexer.js'
export { IndexerTrainer, type RunOnceResult } from './training/indexer-trainer.js'
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
  private closed = false
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
  private indexerTrainer: IndexerTrainer | null = null
  private indexerTrainingConfig: IndexerTrainingConfig = INDEXER_TRAINING_DEFAULTS
  private lightningMode: 'shadow' | 'sparsify' | 'off' = 'off'

  /** Backend for computing text embeddings. 'vllm' = external vLLM (legacy), 'vindex' = gate-vector embedding. */
  private embeddingBackend: 'vllm' | 'vindex' = 'vllm'
  /** Vindex-based embedder function. Set via setVindexEmbedder(). */
  private vindexEmbedder: VindexEmbedder | null = null
  /** Source name of the active vindex (e.g. "default", "trellis2-4b"). */
  private vindexSource: string = 'default'
  /** Feature-indexed retrieval — maps vindex features → engram IDs. */
  readonly featureIndex!: FeatureIndex
  /** HEALPix spatial index — maps engram positions to cells for region queries. */
  readonly spatialIndex: SpatialIndex
  /** Attention-based engram quality scorer (uses forward pass). */
  private qualityScorer: EngramQualityScorer | null = null
  private decomposer: EngramDecomposer | null = null

  /** Pool of backfill worker threads (lazily initialized). */
  private backfillPool: BackfillWorkerPool | null = null
  // Cached after each retrieve() so recordEnrichFeedback can convert
  // helpful/unhelpful into Lightning Indexer training triples without a
  // round-trip to lightning_retrieval_events.
  private lastRetrievalId: string | null = null
  private lastRetrievalCandidates: string[] = []
  private lastRetrievalIndexerScores: Float32Array | null = null
  private lastRetrievalRerankerScores: Float32Array | null = null
  private rerankerEnabled: boolean = false
  private foreshadow: { observe: (args: { query: string; sessionId?: string; wasCacheHit: boolean }) => Promise<void> } | null = null

  // Global Workspace Broadcast state (Phase 1)
  /** Nuclei currently primed by broadcast. In-memory only — lost on restart. */
  private primedNuclei: Map<string, PrimedNucleus> = new Map()
  /** Resonance threshold for nucleus priming. */
  private broadcastResonanceThreshold = BRADCAST_RESONANCE_THRESHOLD

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

  /** Global retrieval counter — incremented on every retrieve(). Used as an
   *  activity-based clock for prime decay instead of wall time. */
  private retrievalCounter: number = 0
  private static readonly PRIME_RETRIEVAL_LIFETIME = 10

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

  /**
   * Set a vindex-based embedding provider for computing gate-vector embeddings.
   * The function should implement the VindexEmbedder signature.
   * When this is set and embeddingBackend is 'vindex', retrieve() and store()
   * use gate-vector embeddings instead of the external vLLM embedding service.
   */
  setVindexEmbedder(embedder: VindexEmbedder | null, source?: string): void {
    this.vindexEmbedder = embedder
    if (source) this.vindexSource = source
    this.logger.info('MnemicField vindex embedder set', { enabled: !!embedder, source: this.vindexSource })
  }

  /**
   * Wire the engram content decomposer for write-time structural decomposition.
   * When set, new engrams get sentence-level feature fingerprints in metadata.
   */
  setDecomposer(decomposer: EngramDecomposer | null): void {
    this.decomposer = decomposer
    if (decomposer) {
      this.consolidationEngine.setDecomposer(decomposer)
    }
    this.logger.info('MnemicField decomposer set', { enabled: !!decomposer })
  }

  /**
   * Wire a forward-capable provider for attention-based quality scoring.
   * Creates the EngramQualityScorer lazily on first call.
   */
  setForwardProvider(provider: ForwardProvider | null): void {
    if (provider && !this.qualityScorer) {
      this.qualityScorer = new EngramQualityScorer(this.logger)
    }
    this.qualityScorer?.setProvider(provider)
    this.logger.info('MnemicField forward provider set', { enabled: !!provider })
  }

  /**
   * Set the embedding backend. 'vllm' (default) uses the external vLLM service.
   * 'vindex' uses the vindex's gate-vector embedding. Requires setVindexEmbedder()
   * to be called first — falls back to 'vllm' if no embedder is registered.
   */
  setEmbeddingBackend(backend: 'vllm' | 'vindex'): void {
    if (backend === 'vindex' && !this.vindexEmbedder) {
      this.logger.warn('Cannot switch to vindex backend — no embedder registered. Staying on vllm.')
      return
    }
    this.embeddingBackend = backend
    this.logger.info('MnemicField embedding backend set', { backend })
  }

  setForeshadow(fs: { observe: (args: { query: string; sessionId?: string; wasCacheHit: boolean }) => Promise<void> } | null): void {
    this.foreshadow = fs
  }

  /**
   * Configure the Lightning Indexer operating mode.
   * - 'off': Indexer not loaded (default)
   * - 'shadow': Indexer scores candidates, logs overlap — does not affect retrieval
   * - 'sparsify': Indexer sparsifies candidates before kindling (top-k + recency window)
   */
  setLightningMode(mode: 'shadow' | 'sparsify' | 'off', trainConfig?: Partial<IndexerTrainingConfig>): void {
    if (trainConfig) {
      this.indexerTrainingConfig = { ...this.indexerTrainingConfig, ...trainConfig }
    }
    this.lightningMode = mode
    if (mode === 'off') {
      this.lightningIndexer = null
      this.indexerTrainer = null
    } else {
      if (!this.lightningIndexer) {
        this.lightningIndexer = new LightningIndexer(this.cortex, this.logger)
      }
      if (!this.indexerTrainer) {
        this.indexerTrainer = new IndexerTrainer(
          this.cortex,
          this.lightningIndexer,
          this.logger,
          this.indexerTrainingConfig,
        )
      }
    }
    this.logger.info('Lightning Indexer mode set', { mode })
  }

  /** Compatibility: enable/disable shadow mode (delegates to setLightningMode). */
  setLightningShadowMode(enabled: boolean): void {
    this.setLightningMode(enabled ? 'shadow' : 'off')
  }

  /**
   * Run one training step for the Lightning Indexer.
   * Returns null if the indexer isn't initialized or no triples available.
   */
  async trainLightningIndexer(): Promise<RunOnceResult | null> {
    if (!this.indexerTrainer || !this.lightningIndexer) return null
    return this.indexerTrainer.runOnce()
  }

  /** Whether the indexer has enough training to leave shadow mode. */
  get indexerReadyForPromotion(): boolean {
    return this.indexerTrainer?.readyForPromotion ?? false
  }

  /** Public status for admin API — avoids (field as any) casts. */
  getLightningStatus(): {
    mode: 'shadow' | 'sparsify' | 'off'
    readyForPromotion: boolean
    trainingSteps: number
    totalTriples: number
    dims: ReturnType<LightningIndexer['stats']> | null
  } {
    return {
      mode: this.lightningMode,
      readyForPromotion: this.indexerReadyForPromotion,
      trainingSteps: this.indexerTrainer?.steps ?? 0,
      totalTriples: this.indexerTrainer?.totalProcessed ?? 0,
      dims: this.lightningIndexer?.stats() ?? null,
    }
  }

  /**
   * Query recent lightning retrieval events. Exposed for Reverie's heuristic labeler
   * so it doesn't need to reach into cortex internals.
   */
  queryLightningRetrievalEvents(opts: {
    sessionId?: string
    since?: string
    limit?: number
  }): LightningRetrievalEvent[] {
    return this.cortex.queryLightningRetrievalEvents(opts)
  }

  /**
   * Batch-fetch engram content, tags, and embeddings for labeling.
   * Uses a single DB query to avoid two round-trips.
   */
  getEngramDataForLabeling(ids: string[]): Map<string, LabelerInputCandidate> {
    const rows = this.cortex.getEngramSummariesWithEmbeddings(ids)
    const out = new Map<string, LabelerInputCandidate>()
    for (const [id, row] of rows) {
      out.set(id, { id: row.id, content: row.content, tags: row.tags, embedding: row.embedding })
    }
    return out
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

      // Crash-recovery WAL checkpoint: after an OOM crash or SIGKILL,
      // the WAL can hold 100 MB+ of un-checkpointed pages.  SQLite replays
      // the WAL synchronously on the first connection, blocking the Node.js
      // event loop (D-state) and making the daemon unresponsive.
      //
      // Open a temporary read-only connection, checkpoint + truncate the
      // WAL, then close.  On clean boots the WAL is already empty so the
      // pragma is a ~1 ms no-op.
      try {
        const recovery = new Database(dbPath, { readonly: true })
        recovery.pragma('wal_checkpoint(TRUNCATE)')
        recovery.close()
      } catch {
        // WHY: DB may not exist yet (first boot) — that's fine.
        // Other errors (permissions, corruption) surface on the real
        // open below.
      }

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
    this.vqPrototypes = new VQSectorPrototypes(1536)  // gate-vector dim (was 1024 Qwen3)
    this.kindlingEngine = new KindlingEngine(this.cortex, logger)
    this.kindlingEngine.setAttractor(this.attractor)
    this.kindlingEngine.setHarmonyProvider(() => this.getHarmony())
    this.kindlingEngine.setBroadcastModProvider((clusterId: string | null) =>
      this.getBroadcastSparkModulation(clusterId))
    this.gradientEngine = new GradientEngine(this.cortex, logger)
    this.consolidationEngine = new ConsolidationEngine(this.cortex, logger, this.gradientEngine, null)
    this.consolidationEngine.setHarmonyProvider(() => this.getHarmony())
    // Phase 0/1: wire vindex FeatureIndex and quality scorer for active field organization
    if (this.featureIndex && this.featureIndex.isReady()) {
      this.consolidationEngine.setFeatureIndex(this.featureIndex as any)
    }
    if (this.qualityScorer && this.qualityScorer.isReady()) {
      this.consolidationEngine.setQualityScorer(this.qualityScorer)
    }
    this.migrationJobs = new MigrationJobStore(db)
    this.affectRegister = new AffectRegister()
    // Use LMDB-backed FeatureIndex (mmap-native, no WAL/checkpoint blocking).
    // Falls back to SQLite if LMDB path is unavailable or explicitly configured.
    const lmdbPath = path.join(path.dirname(db.name), 'feature-index.lmdb')
    try {
      this.featureIndex = new LmdbFeatureIndex(lmdbPath, logger) as unknown as FeatureIndex
      this.logger.info('Using LMDB-backed FeatureIndex', { path: lmdbPath })
    } catch (err) {
      this.logger.warn('LMDB FeatureIndex unavailable, falling back to SQLite', { error: String(err) })
      this.featureIndex = new FeatureIndex(db, logger)
    }
    // Wire FeatureIndex into kindling so seed finding uses vindex features.
    this.kindlingEngine.setFeatureIndex(this.featureIndex)

    // Initialize HEALPix spatial index for position-based queries.
    // Uses the same LMDB environment as the feature index when available.
    this.spatialIndex = new SpatialIndex()
    if ((this.featureIndex as any).env) {
      this.spatialIndex.setEnv((this.featureIndex as any).env)
      this.logger.info('HEALPix SpatialIndex wired to LMDB environment')
    } else {
      this.logger.info('HEALPix SpatialIndex running in-memory (no LMDB env)')
    }
    // Wire spatial index into kindling so kindleByRegion uses O(log cells).
    this.kindlingEngine.setSpatialIndex(this.spatialIndex)

    // Wire embedding provider for slerp-on-merge: FeatureIndex can fetch gate
    // embeddings from the cortex when two engrams merge on feature overlap.
    if (this.featureIndex && typeof (this.featureIndex as any).setEmbeddingProvider === 'function') {
      (this.featureIndex as any).setEmbeddingProvider((id: string) =>
        this.cortex.getEngramEmbeddings([id]).get(id) ?? null)
    }

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

    // Strip conversation preamble before embedding — 26% of engrams start with
    // "USER: (context)\n\nASSISTANT:" which dilutes embeddings and fingerprints.
    const cleanedContent = stripConversationPreamble(input.content)

    // Auto-embed with vindex gate vectors when backend is active and no explicit
    // embedding was provided. This closes the loop: every new engram enters the
    // model's native representation space without separate vLLM embedding pass.
    let resolvedEmbedding = input.embedding
    if (!resolvedEmbedding && this.embeddingBackend === 'vindex' && this.vindexEmbedder) {
      const vec = this.vindexEmbedder(cleanedContent, { minScore: 0.05 })
      if (vec) resolvedEmbedding = vec
    }

    let x = input.x
    let y = input.y
    let z = input.z
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
        // Derive z from embedding residual: mean difference from assigned VQ prototype.
        // Positive z = engram is "above" its prototype (novel variation);
        // negative z = "below" (simpler than the prototype).
        if (z === undefined) {
          const prototype = this.vqPrototypes.codebook[assignedIdx]
          if (prototype) {
            let sumResidual = 0
            for (let i = 0; i < emb.length; i++) {
              sumResidual += emb[i] - prototype[i]
            }
            z = sumResidual / emb.length
          } else {
            z = 0
          }
        }
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

    if (z === undefined) z = 0

    const affect = attune(cleanedContent)
    let metadata: Record<string, unknown> = { ...input.metadata ?? {}, affect, r, theta, z }

    // Tag engram with the vindex source that produced its embedding.
    if (this.embeddingBackend === 'vindex' && this.vindexEmbedder) {
      metadata = { ...metadata, vindexSource: this.vindexSource }
    }

    // Contrastive retrieval feedback: link new engrams to the luminal
    // engrams that triggered their creation via the most recent retrieval.
    if (this.lastLuminalIds.length > 0) {
      metadata = { ...metadata, triggeredBy: [...this.lastLuminalIds] }
      this.lastLuminalIds = []
    }

    const engram = this.cortex.createEngram({ ...input, content: cleanedContent, x, y, z, metadata, embedding: resolvedEmbedding })

    // Index in HEALPix SpatialIndex for O(log cells) region queries.
    // Runs best-effort — index failures don't block engram creation.
    if (this.spatialIndex?.ready) {
      try {
        this.spatialIndex.indexEngram({
          engramId: engram.id,
          r, theta, z,
          potentiation: engram.potentiation,
          nodeType: engram.nodeType ?? 'unknown',
          contentPreview: (cleanedContent ?? '').slice(0, 100),
        })
      } catch (err) {
        this.logger.debug('spatialIndex.indexEngram skipped', { engramId: engram.id, error: String(err) })
      }
    }

    // Index in FeatureIndex for direct feature-indexed retrieval.
    // If gateKnn finds a near-complete feature overlap (≥95%) with an
    // existing engram, the index merges them — we boost the anchor's
    // potentiation and skip synapse creation.
    if (this.featureIndex?.isReady()) {
      try {
        const result = this.featureIndex.indexEngram(engram.id, cleanedContent, {
          embedding: resolvedEmbedding ?? undefined,
        })

        if (result.action === 'merged' && result.mergedInto) {
          // Boost the anchor engram's potentiation, scaled by feature richness.
          const anchor = this.cortex.getEngram(result.mergedInto)
          if (anchor) {
            const featureCount = result.featureCount ?? 10
            const boost = 0.02 * Math.min(1.0, featureCount / 40)
            this.cortex.updateEngram(result.mergedInto, {
              potentiation: Math.min(1.0, anchor.potentiation + boost),
            })

            // Persist slerped embedding computed by the FeatureIndex merge
            if (result.slerpedEmbedding) {
              this.cortex.bulkUpdateEmbeddings([{ id: result.mergedInto, embedding: result.slerpedEmbedding }])
            }
          }
          // Skip synapse creation — the new engram was merged, not indexed.
        } else {
          // Indexed normally — create vindex_correlation synapses.
          const correlated = this.featureIndex.findCorrelated(engram.id, {
            minOverlap: 2,
            limit: 10,
          })
          for (const corr of correlated) {
            const weight = Math.min(1.0, corr.sharedFeatureCount / 10)
            try {
              this.cortex.createSynapse({
                sourceId: engram.id,
                targetId: corr.engramId,
                edgeType: 'vindex_correlation',
                weight,
                metadata: { sharedFeatures: corr.sharedFeatureCount },
              })
            } catch { /* duplicate synapse — silently skip */ }
          }
        }
      } catch { /* best-effort */ }
    }

    // Write spherical position to the position-index (V1).
    // φ derived from z residual: tanh-normalized → arccos → [0, π].
    if (this.featureIndex?.isReady()) {
      const normZ = Math.max(-1, Math.min(1, Math.tanh(z! * 5)))
      const phi = Math.acos(normZ)
      const emb = resolvedEmbedding instanceof Float32Array ? resolvedEmbedding : undefined
      this.featureIndex.writePosition(engram.id, r!, theta!, phi, emb)
    }

    // Fire-and-forget: decompose content into structural layers.
    // Adds sentence-level feature fingerprints to metadata for read-time
    // selection. Don't block the store — use setImmediate.
    if (this.decomposer?.isReady()) {
      const engramId = engram.id
      const content = cleanedContent
      const existingMeta = engram.metadata
      setImmediate(() => {
        try {
          const result = this.decomposer!.decompose(content)
          if (result && result.entries.length > 0) {
            const sentencesMeta = {
              vindexVersion: result.vindexVersion,
              entries: result.entries,
            }
            this.cortex.updateEngram(engramId, {
              metadata: { ...existingMeta, sentences: sentencesMeta },
            })
          }
          // Always store density metrics even if no sentence features
          if (result?.density) {
            this.cortex.updateEngram(engramId, {
              metadata: { ...this.cortex.getEngram(engramId)?.metadata, density: result.density },
            })
          }
        } catch { /* best-effort */ }
      })
    }

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
   * Side-effect-free, no-log FTS lookup for privacy-sensitive provider-context
   * selection. SQLite failures propagate to the caller instead of being logged
   * with or converted from the raw query.
   */
  searchTextStrict(query: string, limit?: number): EngramSearchResult[] {
    const results = this.cortex.searchTextStrict(query, limit)
    return results.filter(result => result.engram.nodeType !== 'bridge')
  }

  /**
   * Worker-isolated strict FTS lookup. Provider-context candidates never run
   * synchronous SQLite on the runtime event loop; an in-memory field has no
   * separately openable read-only database and therefore fails open at the
   * candidate service rather than silently violating its deadline.
   */
  async searchTextStrictAsync(query: string, limit = 20, timeoutMs = 300): Promise<EngramSearchResult[]> {
    const dbPath = this.db.name
    if (!dbPath || dbPath === ':memory:') throw new Error('mnemic-strict-search-unavailable')

    const worker = new Worker(fileURLToPath(new URL(
      './fts-search-worker.js',
      import.meta.url,
    )), {
      workerData: { dbPath, query, limit },
    })
    try {
      const signal = AbortSignal.timeout(Math.max(1, Math.min(timeoutMs, 5_000)))
      const [reply] = await once(worker, 'message', { signal }) as [{
        ok: boolean
        results?: EngramSearchResult[]
        error?: string
      }]
      if (!reply.ok || !reply.results) throw new Error(reply.error ?? 'fts-search-failed')
      return reply.results
    } finally {
      await worker.terminate()
    }
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
    // Uses vindex gate-vector embedding when configured, otherwise falls back
    // to the external vLLM embedding service.
    let queryEmbedding: number[] | null = null
    if (this.embeddingBackend === 'vindex' && this.vindexEmbedder) {
      const vec = this.vindexEmbedder(query, { minScore: 0.05 })
      queryEmbedding = vec ? Array.from(vec) : null
      this.logger.info('vindex embedder result', { hasEmbedding: queryEmbedding !== null, dim: queryEmbedding?.length ?? 0, queryLen: query.length })
    } else {
      const embSvc = getEmbeddingService(this.logger)
      queryEmbedding = embSvc.available ? await embSvc.embed(query, 'query') : null
    }

    return this._retrieveWithEmbedding(queryEmbedding, query, retrievalId, cacheKey, now, options, limit)
  }

  /**
   * Shared retrieval pipeline — kindling → FeatureIndex → reranking → structural
   * filter → broadcast → activation → cache. Both retrieve() and retrieveWithPatch()
   * call this; the only difference is how the query embedding is generated.
   */
  private async _retrieveWithEmbedding(
    queryEmbedding: number[] | null,
    query: string,
    retrievalId: string,
    cacheKey: string,
    now: number,
    options: (KindlingOptions & { limit?: number; sessionId?: string }) | undefined,
    limit: number,
  ): Promise<MnemicRetrievalHit[]> {
    let hits: MnemicRetrievalHit[] = []

    // Step 1: Kindling generates candidate engrams via engram ANN + synapse spread.
    const luminal = this.kindle(queryEmbedding, query, {
      ...options,
      maxLuminalSize: limit * 3,
      maxIterations: 2,
      maxSeeds: Math.max(options?.maxSeeds ?? 20, limit * 4),
      includeText: true,
      currentAffect: options?.currentAffect ?? this.affectRegister.getAffect(),
    })

    // FeatureIndex: direct feature-indexed retrieval — complements the ANN path.
    if (this.featureIndex?.isReady()) {
      try {
        const fiHits = this.featureIndex.lookup(query, {
          featuresPerLayer: 10,
          minScore: 0.05,
          limit: limit * 2,
        })
        if (fiHits.length > 0) {
          const existingIds = new Set(luminal.engrams.map(e => e.engram.id))
          const novelHits = fiHits.filter(h => !existingIds.has(h.engramId))
          if (novelHits.length > 0) {
            const maxOverlap = Math.max(...novelHits.map(h => h.sharedFeatureCount))
            const novelEngrams = this.cortex.getEngrams(novelHits.map(h => h.engramId))
            for (const hit of novelHits) {
              const engram = novelEngrams.get(hit.engramId)
              if (engram && engram.nodeType !== 'bridge') {
                const charge = maxOverlap > 0
                  ? (hit.sharedFeatureCount / maxOverlap) * 0.6
                  : 0
                if (charge > 0.1) {
                  luminal.engrams.push({ engram, charge })
                }
              }
            }
            this.logger.debug('FeatureIndex added candidates', {
              novel: novelHits.length,
              maxOverlap,
              luminalSize: luminal.engrams.length,
            })
          }
        }
      } catch (err) {
        this.logger.debug('FeatureIndex lookup failed', { error: String(err) })
      }
    }

    // Track luminal engram IDs for retrieval chain continuity.
    this.lastLuminalIds = luminal.engrams.map(e => e.engram.id)

    // Compute harmony metric after each kindling cycle (fire-and-forget).
    setImmediate(() => {
      if (this.closed) return
      try { this.computeHarmony() } catch { /* non-blocking */ }
    })

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
      let candidates = luminal.engrams.map(hit => hit.engram)

      // Lightning Indexer: score candidates.
      if (this.lightningIndexer && queryEmbedding && this.lightningMode !== 'off') {
        try {
          const idxCandidates = candidates
            .filter(e => e.embedding && e.embedding.length > 0)
            .map(e => ({ engramId: e.id, embedding: e.embedding as Float32Array }))
          if (idxCandidates.length > 0) {
            const qEmb = new Float32Array(queryEmbedding)

            if (this.lightningMode === 'sparsify') {
              const { sparsifyTopK, recencyWindow } = this.indexerTrainingConfig
              const { keptIds, ranked } = this.lightningIndexer.sparsify(qEmb, idxCandidates, sparsifyTopK, recencyWindow)
              const keptSet = new Set(keptIds)
              const filtered = luminal.engrams.filter(h => keptSet.has(h.engram.id))
              if (filtered.length > 0) {
                (luminal as { engrams: typeof luminal.engrams }).engrams = filtered
                candidates = filtered.map(hit => hit.engram)
                this.logger.debug('Indexer sparsified candidates', {
                  before: idxCandidates.length,
                  after: keptIds.length,
                  topK: sparsifyTopK,
                  recency: recencyWindow,
                })
              }
              lightningRanked = ranked
            } else {
              lightningRanked = this.lightningIndexer.score(qEmb, idxCandidates)
            }
          }
        } catch (err) {
          this.logger.debug('Lightning indexer failed', { error: String(err) })
        }
      }

      // Step 2: Rerank candidates using the configured reranker mode.
      if (this.rerankerMode === 'local') {
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
          k, overlap, overlapRatio: overlap / k,
          lightningTopScore: lightningRanked[0]?.score ?? 0,
          candidateCount: lightningRanked.length,
        })
      }
    }

    // Persist retrieval event for Reverie labeling (best-effort).
    try {
      const candidateIds = hits.map(h => h.id)
      const sessionId = options?.sessionId
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

      const mode: LightningRetrievalMode =
        this.lightningMode === 'sparsify' ? 'live' :
        this.rerankerMode === 'local'
          ? (lightningRanked ? 'shadow' : 'kindle-only')
          : lightningRanked ? 'shadow' : (this.rerankerMode === 'llm' ? 'shadow' : 'kindle-only')

      this.lastRetrievalId = retrievalId
      this.lastRetrievalCandidates = candidateIds
      this.lastRetrievalIndexerScores = indexerScoresArr ?? null
      this.lastRetrievalRerankerScores = rerankerScoresArr ?? null

      this.cortex.recordLightningRetrievalEvent({
        retrievalId, sessionId,
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

    // Filter structural engrams from user-facing results.
    const contentHits = hits.filter(h => !STRUCTURAL_TYPES.has(h.nodeType))
    this.logger.info('retrieve structural filter', { before: hits.length, after: contentHits.length, types: [...new Set(hits.map(h => h.nodeType))].join(',') })

    // Global Workspace Broadcast + activation recording (fire-and-forget).
    try {
      this.retrievalCounter++
      this.broadcastGlobalWorkspace(hits.map(h => h.id))
    } catch (err) {
      this.logger.debug('Global workspace broadcast failed', { error: String(err) })
    }
    try {
      this.recordActivation(luminal)
    } catch (err) {
      this.logger.debug('Activation recording failed', { error: String(err) })
    }

    // Cache result.
    this.retrieveCache.set(cacheKey, { hits: contentHits, ts: now })
    while (this.retrieveCache.size > MnemicField.RETRIEVE_CACHE_MAX) {
      const oldest = this.retrieveCache.keys().next().value
      if (oldest === undefined) break
      this.retrieveCache.delete(oldest)
    }
    return contentHits
  }

  /**
   * Kindling retrieval anchored at a spatial point.
   *
   * Finds engrams within `radius` of the spherical-coordinate target
   * using the HEALPix spatial index (O(log cells)), then runs the full
   * kindling pipeline (seed → spread → photon → ignite) on them as
   * privileged seeds. Falls back to O(n) linear scan if the spatial
   * index isn't available.
   */
  retrieveByRegion(
    r: number,
    theta: number,
    z: number,
    radius: number,
    options?: KindlingOptions,
  ) {
    return this.kindlingEngine.kindleByRegion(r, theta, z, radius, options ?? {})
  }

  /**
   * Causal retrieval: embed with feature patching to shift the result set.
   *
   * This is the architectural proof: the model's representation space IS
   * the retrieval space, and you can intervene on it causally. Boosting a
   * feature shifts the embedding toward that feature's concept direction,
   * producing observably different retrieval results without changing the
   * query text.
   *
   * @example
   *   // Get features for "attention mechanism"
   *   const hits = gateKnn("attention mechanism", 16, 10)
   *   // Patch the top feature 3× — should shift results toward attention concepts
   *   const patched = await field.retrieveWithPatch("attention mechanism",
   *     [{ layer: 16, featureIndex: hits[0].featureIndex, boost: 3.0 }])
   */
  async retrieveWithPatch(
    query: string,
    patches: Array<{ layer: number; featureIndex: number; boost: number }>,
    options?: KindlingOptions & { limit?: number; sessionId?: string },
  ): Promise<MnemicRetrievalHit[]> {
    if (this.embeddingBackend !== 'vindex' || !this.vindexEmbedder) {
      return this.retrieve(query, options)
    }

    // Generate patched embedding.
    const vec = this.vindexEmbedder(query, { minScore: 0.05, patches })
    const patchedEmbedding = vec ? Array.from(vec) : null

    // Use a unique cache key — patched queries are inherently varied (different
    // patches produce different embeddings), so caching offers little benefit.
    const limit = options?.limit ?? 8
    const retrievalId = randomUUID()
    const now = Date.now()
    const cacheKey = `patch:${retrievalId}`

    return this._retrieveWithEmbedding(patchedEmbedding, query, retrievalId, cacheKey, now, options, limit)
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

    // Modulate attractor alpha weights based on harmony
    this.attractor.applyHarmonyModulation(this.lastHarmony)

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
  private broadcastGlobalWorkspace(luminalIds: string[]): BroadcastResult | null {
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

    // Shift attractor's broadcast pole toward the workspace centroid
    this.attractor.shiftToward(broadcastX, broadcastY)

    // Expire primed nuclei past their retrieval lifetime
    const stamp = this.retrievalCounter
    for (const [id, prime] of this.primedNuclei) {
      if (stamp - prime.retrievalStamp >= MnemicField.PRIME_RETRIEVAL_LIFETIME) {
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
          retrievalStamp: stamp,
        })
        nucleiPrimed++
      } else {
        nucleiIgnored++
      }
    }

    // Hub cascade: hub engrams in the luminal set re-broadcast to their
    // bridged nuclei at reduced strength (50%). One-hop only — cascaded
    // nuclei do not cascade further. Uses FeatureIndex neighbor nucleus diversity.
    const HUB_CASCADE_FACTOR = 0.5
    let hubCascadeCount = 0
    const fiReady = this.featureIndex.isReady()

    for (const [engramId, engram] of luminalEngrams) {
      const hubScore = (engram.metadata as Record<string, unknown>)?.hubScore as number | undefined
      if (!hubScore || hubScore < 0.3 || !fiReady) continue

      // Find bridged nuclei via FeatureIndex neighbors
      const correlated = this.featureIndex.findCorrelated(engramId, { limit: 50, minOverlap: 1 })
      const neighbors = correlated.map(c => ({ id: c.engramId, distance: 1 - c.sharedFeatureCount / (c.sharedFeatureCount + 10) }))
      // Batch-fetch neighbor engrams (1 query instead of N)
      const neighborIds = neighbors
        .filter(n => n.id !== engramId)
        .map(n => n.id)
      const neighborEngrams = this.cortex.getEngrams(neighborIds)
      const bridgedNuclei = new Set<string>()
      for (const nId of neighborIds) {
        const neighborEngram = neighborEngrams.get(nId)
        if (neighborEngram?.clusterId) {
          bridgedNuclei.add(neighborEngram.clusterId)
        }
      }

      // Calculate hub's effective resonance (based on its spatial position, including z)
      const hubR = Math.sqrt(engram.x * engram.x + engram.y * engram.y + (engram.z ?? 0) * (engram.z ?? 0))
      const hubResonance = 1 / (1 + hubR)

      // Cascade to each bridged nucleus at reduced strength
      for (const nucleusId of bridgedNuclei) {
        const cascadeResonance = hubResonance * HUB_CASCADE_FACTOR
        const existing = this.primedNuclei.get(nucleusId)
        if (!existing || cascadeResonance > existing.resonance) {
          this.primedNuclei.set(nucleusId, {
            nucleusId,
            resonance: cascadeResonance,
            retrievalStamp: stamp,
          })
          hubCascadeCount++
        }
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
      hubCascadeCount,
      totalNuclei: allNuclei.length,
      durationMs,
    })

    return { nucleiPrimed, nucleiIgnored, broadcastX, broadcastY, durationMs, totalNuclei: allNuclei.length }
  }

  /**
   * Get the current spark point modulation for an engram.
   * If the engram belongs to a primed nucleus, its spark point is lowered
   * (making it easier to ignite). Returns 1.0 (no modulation) if not primed.
   *
   * Called from KindlingEngine during ignite.
   */
  getBroadcastSparkModulation(clusterId: string | null): number {
    if (!clusterId) return 1.0

    const prime = this.primedNuclei.get(clusterId)
    if (!prime || this.retrievalCounter - prime.retrievalStamp >= MnemicField.PRIME_RETRIEVAL_LIFETIME) return 1.0

    // Modulation: 1.0 (no change) -> MIN_SPARK_MODULATION (max lowering)
    // Higher resonance = stronger lowering
    return 1.0 - (1.0 - MIN_SPARK_MODULATION) * prime.resonance
  }

  /** Return currently primed nuclei (for admin API observability). */
  getPrimedNuclei(): Array<{ nucleusId: string; resonance: number; remainingRetrievals: number }> {
    return [...this.primedNuclei.values()]
      .filter(p => this.retrievalCounter - p.retrievalStamp < MnemicField.PRIME_RETRIEVAL_LIFETIME)
      .map(p => ({
        nucleusId: p.nucleusId, resonance: p.resonance,
        remainingRetrievals: MnemicField.PRIME_RETRIEVAL_LIFETIME - (this.retrievalCounter - p.retrievalStamp),
      }))
  }

  /** 
   * Compute the fractal dimension of the field using box-counting.
   * Grids the 3D space (x, y, z) at multiple resolutions and fits
   * log(count) vs log(1/boxSize) — the slope is the fractal dimension.
   * 
   * Samples up to 5000 engrams for efficiency. A healthy field should
   * have dimension between 1.2 and 1.8.
   */
  getFractalDimension(): number {
    const sampleSize = 5000
    const engrams = this.cortex.listEngrams(sampleSize)
    if (engrams.length < 10) return 0

    // Extract 3D positions
    const points = engrams.map(e => ({
      x: e.x ?? 0,
      y: e.y ?? 0,
      z: e.z ?? 0,
    }))

    // Compute bounding box
    let minX = Infinity, maxX = -Infinity
    let minY = Infinity, maxY = -Infinity
    let minZ = Infinity, maxZ = -Infinity
    for (const p of points) {
      if (p.x < minX) minX = p.x
      if (p.x > maxX) maxX = p.x
      if (p.y < minY) minY = p.y
      if (p.y > maxY) maxY = p.y
      if (p.z < minZ) minZ = p.z
      if (p.z > maxZ) maxZ = p.z
    }

    const spanX = maxX - minX || 1
    const spanY = maxY - minY || 1
    const spanZ = maxZ - minZ || 1
    const maxSpan = Math.max(spanX, spanY, spanZ)

    // Box sizes: powers of 2 from maxSpan down to maxSpan/128
    const boxes: number[] = []
    for (let size = maxSpan; size > maxSpan / 128; size /= 2) {
      boxes.push(size)
    }
    if (boxes.length < 3) return 0

    // Count occupied boxes at each resolution
    const logCounts: number[] = []
    const logInvSizes: number[] = []

    for (const boxSize of boxes) {
      const occupied = new Set<number>()
      for (const p of points) {
        const bx = Math.floor((p.x - minX) / boxSize)
        const by = Math.floor((p.y - minY) / boxSize)
        const bz = Math.floor((p.z - minZ) / boxSize)
        occupied.add((bx & 0x3FF) | ((by & 0x3FF) << 10) | ((bz & 0x3FF) << 20))
      }
      const count = occupied.size
      if (count > 0) {
        logCounts.push(Math.log(count))
        logInvSizes.push(Math.log(1 / boxSize))
      }
    }

    if (logCounts.length < 3) return 0

    // Linear regression: slope = fractal dimension
    const n = logCounts.length
    let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0
    for (let i = 0; i < n; i++) {
      sumX += logInvSizes[i]
      sumY += logCounts[i]
      sumXY += logInvSizes[i] * logCounts[i]
      sumX2 += logInvSizes[i] * logInvSizes[i]
    }
    const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX)

    return Math.max(0, Math.min(3, slope))
  }

  /**
   * Split text into sentences — simple, deterministic, no NLP deps.
   * Splits on sentence-final punctuation followed by whitespace.
   */
  private _splitSentences(text: string, maxLen = 500): string[] {
    if (!text) return []
    const blocks = text.split(/\n\s*\n+|\n\s*[-*]\s+/g).map(b => b.trim()).filter(Boolean)
    const out: string[] = []
    for (const block of blocks) {
      const parts = block.split(/(?<=[.!?])\s+(?=[A-Z"'])/g).map(s => s.trim()).filter(Boolean)
      for (const p of parts) {
        if (p.length <= maxLen) {
          out.push(p)
        } else {
          // Long sentence/run-on — chunk it
          for (let i = 0; i < p.length; i += maxLen) {
            out.push(p.slice(i, i + maxLen))
          }
        }
      }
    }
    return out
  }

  /**
   * Contrastive Extraction (Phase 2): For engrams within the same angular sector
   * or nucleus, cancels out shared text and surfaces what's unique.
   *
   * Groups engrams by nucleus (clusterId) and by angular sector (theta).
   * For each group, splits content into sentences, embeds them, and compares
   * cosine similarity. Shared sentences (sim >= 0.75 across engrams) are
   * removed; unique sentences form the distinctiveContent.
   *
   * Stores distinctiveness score and distinctive content on each engram's
   * metadata. Runs per angular sector so all positioned engrams get scored,
   * even those not yet assigned to a nucleus.
   *
   * Called during consolidation, after nucleus detection.
   *
   * @param maxEngramsPerGroup cap on group size to bound embedding cost (default 50)
   * @returns summary of engrams scored and groups processed
   */
  async extractDistinctiveness(maxEngramsPerGroup = 50): Promise<{
    engramsScored: number
    groupsProcessed: number
    durationMs: number
  }> {
    const start = Date.now()
    let engramsScored = 0
    let groupsProcessed = 0

    try {
      // Lean query: only fetch fields needed for grouping + content.
      // Avoids pulling large embedding BLOBs into memory.
      const rows = this.db.prepare(`
        SELECT id, content, cluster_id, x, y, metadata
        FROM engrams
        WHERE content IS NOT NULL AND length(content) > 20
      `).all() as Array<{
        id: string; content: string; cluster_id: string | null
        x: number; y: number; metadata: string | null
      }>

      // Group engrams by nucleus (clusterId) and angular sector
      const nucleusGroups = new Map<string, Array<{ id: string; content: string }>>()
      const sectorGroups = new Map<number, Array<{ id: string; content: string }>>()

      for (const row of rows) {
        // Nucleus grouping
        if (row.cluster_id) {
          let g = nucleusGroups.get(row.cluster_id)
          if (!g) { g = []; nucleusGroups.set(row.cluster_id, g) }
          if (g.length < maxEngramsPerGroup) g.push({ id: row.id, content: row.content })
        }

        // Sector grouping: derive theta from metadata or x/y
        let theta: number | null = null
        if (row.metadata) {
          try {
            const meta = JSON.parse(row.metadata)
            if (typeof meta.theta === 'number') theta = meta.theta
          } catch { /* malformed metadata, ignore */ }
        }
        if (theta === null && row.x !== undefined && row.y !== undefined && (row.x !== 0 || row.y !== 0)) {
          theta = Math.atan2(row.y, row.x)
        }
        if (theta !== null) {
          const sector = Math.floor(normalizeTheta(theta) / SECTOR_SIZE) % DEFAULT_SECTOR_COUNT
          let g = sectorGroups.get(sector)
          if (!g) { g = []; sectorGroups.set(sector, g) }
          if (g.length < maxEngramsPerGroup) g.push({ id: row.id, content: row.content })
        }
      }

      this.logger.info('Contrastive extraction: groups built', {
        nucleusGroups: nucleusGroups.size,
        sectorGroups: sectorGroups.size,
        totalEngrams: rows.length,
      })

      const embSvc = getEmbeddingService(this.logger)

      // Helper: score one group
      const scoreGroup = async (
        members: Array<{ id: string; content: string }>,
        groupKey: string,
      ): Promise<number> => {
        if (members.length < 2) return 0

        // Split each member into sentences
        const perEngram: Array<{ id: string; sentences: string[] }> = []
        const allSentences: string[] = []
        for (const eng of members) {
          const sentences = this._splitSentences(eng.content, 500)
            .filter(s => s.length > 10)
          if (sentences.length === 0) continue
          perEngram.push({ id: eng.id, sentences })
          for (const s of sentences) allSentences.push(s)
        }

        if (allSentences.length < 2 || perEngram.length < 2) return 0

        // Batch embed all sentences
        const embeddings = await embSvc.embedBatch(allSentences, 'document')

        // Build index → embedding
        const sentEmb = new Map<number, number[]>()
        for (let i = 0; i < embeddings.length; i++) {
          if (embeddings[i]) sentEmb.set(i, embeddings[i]!)
        }

        const SIM_THRESHOLD = 0.75
        let offset = 0
        let scored = 0

        for (const eng of perEngram) {
          const n = eng.sentences.length
          const uniqueIndices: number[] = []

          for (let i = 0; i < n; i++) {
            const myIdx = offset + i
            const myEmb = sentEmb.get(myIdx)
            if (!myEmb) { uniqueIndices.push(i); continue }

            let isShared = false
            // Compare against all OTHER engrams' sentences
            for (const [otherIdx, otherEmb] of sentEmb) {
              if (otherIdx >= offset && otherIdx < offset + n) continue
              const sim = cosineSimilarity(myEmb, otherEmb)
              if (sim >= SIM_THRESHOLD) { isShared = true; break }
            }

            if (!isShared) uniqueIndices.push(i)
          }

          const score = n > 0 ? uniqueIndices.length / n : 0
          const distinctiveContent = uniqueIndices.map(i => eng.sentences[i]).join(' ')

          // Merge into existing metadata to avoid blowing away other keys
          try {
            const existing = this.cortex.getEngram(eng.id)
            const baseMeta: Record<string, unknown> = existing?.metadata
              ? { ...existing.metadata as Record<string, unknown> }
              : {}
            baseMeta.distinctiveness = {
              score,
              distinctiveContent,
              totalSentences: n,
              uniqueSentences: uniqueIndices.length,
              groupKey,
            } satisfies import('./types.js').DistinctivenessResult
            this.cortex.updateEngram(eng.id, { metadata: baseMeta })
            scored++
          } catch (err) {
            this.logger.warn('Failed to update engram distinctiveness', {
              engramId: eng.id, error: String(err),
            })
          }

          offset += n
        }

        return scored
      }

      // Process nucleus groups
      for (const [nucleusId, members] of nucleusGroups) {
        if (members.length < 2) continue
        const scored = await scoreGroup(members, nucleusId)
        engramsScored += scored
        groupsProcessed++
        // Yield to event loop between groups
        await new Promise(resolve => setImmediate(resolve))
      }

      // Process sector groups
      for (const [sectorIdx, members] of sectorGroups) {
        if (members.length < 2) continue
        const scored = await scoreGroup(members, `sector-${sectorIdx}`)
        engramsScored += scored
        groupsProcessed++
        await new Promise(resolve => setImmediate(resolve))
      }
    } catch (err) {
      this.logger.error('Contrastive extraction failed', { error: String(err) })
    }

    const durationMs = Date.now() - start
    this.logger.info('Contrastive extraction complete', {
      engramsScored, groupsProcessed, durationMs,
    })
    return { engramsScored, groupsProcessed, durationMs }
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
    runner: Pick<typeof import('./vendor/core/intelligence/embeddings/embedding-service.js'), never> | null,
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

  getNucleus(id: string): Nucleus | null {
    return this.cortex.getNucleus(id)
  }

  getEngramsByCluster(clusterId: string): Engram[] {
    return this.cortex.getEngramsByCluster(clusterId)
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
    // Use vindex gate-vector embedding when configured, otherwise fall back
    // to the external vLLM embedding service.
    const useVindex = this.embeddingBackend === 'vindex' && this.vindexEmbedder
    let embSvc: ReturnType<typeof getEmbeddingService> | null = null
    if (!useVindex) {
      embSvc = getEmbeddingService(this.logger)
      if (!embSvc.available) {
        throw new Error('Embedding service not available')
      }
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
      let vec: Float32Array | number[] | null = null
      if (useVindex) {
        vec = this.vindexEmbedder!(content, { minScore: 0.05 })
      } else {
        vec = await embSvc!.embed(content, 'document')
      }
      if (!vec) continue
      this.cortex.updateEngram(id, { embedding: vec })

      // Incremental projection: place via k-NN if we have state
      if (this.projectionState) {
        const pos = projectSingle(Array.from(vec), this.projectionState)
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
      const missing = this.cortex.getEngramsNeedingBackfill(BATCH_SIZE)
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

  /**
   * Detect hub engrams: engrams whose embedding-space neighbors span
   * many distinct nuclei. Hubs are field-level concepts — their content
   * is relevant across unrelated domains.
   *
   * Samples up to 5000 embedded engrams. Stores hubScore on metadata.
   * Returns hubs with score above threshold (0.3 = spans 30%+ of sampled
   * nuclei within neighbor radius).
   */
  detectHubs(options?: { sampleLimit?: number; neighborK?: number; hubThreshold?: number }): Array<{ engramId: string; hubScore: number; distinctNuclei: number }> {
    const sampleLimit = options?.sampleLimit ?? 5000
    const neighborK = options?.neighborK ?? 50
    const hubThreshold = options?.hubThreshold ?? 0.3

    if (!this.featureIndex?.isReady()) {
      this.logger.debug('Hub detection skipped — FeatureIndex not ready')
      return []
    }

    // Get sample of engrams with embeddings
    const vectors = this.cortex.getEmbeddingVectors(sampleLimit)
    if (vectors.length === 0) return []

    const allNuclei = this.cortex.listNuclei()
    const nucleusSet = new Set(allNuclei.map(n => n.id))
    const hubs: Array<{ engramId: string; hubScore: number; distinctNuclei: number }> = []

    for (const { id, embedding } of vectors) {
      const correlated = this.featureIndex.findCorrelated(id, { limit: neighborK + 1, minOverlap: 1 })
      const neighbors = correlated.map(c => ({ id: c.engramId, distance: 1 - c.sharedFeatureCount / (c.sharedFeatureCount + 10) }))

      // Count distinct nuclei among neighbors
      const nucleiSeen = new Set<string>()
      for (const n of neighbors) {
        if (n.id === id) continue
        const neighborEngram = this.cortex.getEngram(n.id)
        if (neighborEngram?.clusterId && nucleusSet.has(neighborEngram.clusterId)) {
          nucleiSeen.add(neighborEngram.clusterId)
        }
      }

      const distinctNuclei = nucleiSeen.size
      const hubScore = nucleusSet.size > 0
        ? distinctNuclei / Math.min(neighborK, nucleusSet.size)
        : 0

      // Store on metadata for retrieval-time use
      if (hubScore > 0) {
        const engram = this.cortex.getEngram(id)
        if (engram) {
          const existingMeta = (engram.metadata ?? {}) as Record<string, unknown>
          this.cortex.updateEngram(id, {
            metadata: { ...existingMeta, hubScore, distinctNuclei, computedAt: Date.now() }
          })
        }

        if (hubScore >= hubThreshold) {
          hubs.push({ engramId: id, hubScore, distinctNuclei })
        }
      }
    }

    this.logger.info('Hub detection complete', {
      sampled: vectors.length,
      hubsFound: hubs.length,
      topScore: hubs[0]?.hubScore?.toFixed(3) ?? 0,
    })

    return hubs.sort((a, b) => b.hubScore - a.hubScore)
  }

  /**
   * Return engrams previously identified as hubs (from metadata).
   */
  getHubs(limit = 20): Array<{ engramId: string; hubScore: number; content: string }> {
    // SQL filter avoids loading all engrams into memory
    const rows = this.db.prepare(`
      SELECT id, content, json_extract(metadata, '$.hubScore') as hubScore
      FROM engrams
      WHERE json_extract(metadata, '$.hubScore') > 0.3
      ORDER BY json_extract(metadata, '$.hubScore') DESC
      LIMIT ?
    `).all(limit) as Array<{ id: string; content: string; hubScore: number }>
    return rows.map(r => ({
      engramId: r.id,
      hubScore: r.hubScore,
      content: r.content.slice(0, 200),
    }))
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
   * Update the global attention consensus from active Helix session embeddings.
   * The consolidation engine computes a spherical centroid and uses it
   * as the geodesic drift attractor during centripetal drift.
   *
   * Call from the Constellation orchestrator after each Helix session turn.
   */
  updateActiveAttentionEmbeddings(sessionEmbeddings: Float32Array[]): void {
    this.consolidationEngine.setActiveSessionEmbeddings(sessionEmbeddings)
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

    const result = await this.consolidationEngine.consolidate(options)

    // Assign orphaned engrams to their nearest nucleus by 3D distance.
    // DBSCAN clustering is tight (ε=0.015) and leaves ~96% of engrams
    // unassigned. Nearest-neighbor assignment fills the gaps.
    if (!options?.skipOrphanAssignment) {
      try {
        const count = this.assignOrphansToNearestNucleus()
        this.logger.info('Orphan engrams assigned to nuclei', { assigned: count })
      } catch (err) {
        this.logger.warn('Orphan assignment failed', { error: String(err) })
      }
    }

    // Phase 2: Contrastive Extraction — after nuclei and drift settle,
    // cancel shared sentences within each group to surface what's unique.
    if (!options?.skipDistinctiveness) {
      try {
        const de = await this.extractDistinctiveness()
        result.distinctivenessEngramsScored = de.engramsScored
        result.distinctivenessGroupsProcessed = de.groupsProcessed
        result.distinctivenessDurationMs = de.durationMs
      } catch (err) {
        this.logger.warn('Distinctiveness extraction failed', { error: String(err) })
      }
    }

    // Invalidate photon feature-overlap cache after consolidation
    this.kindlingEngine.invalidatePhotonCache()

    // Lightning Indexer training: run if triples are available
    if (this.lightningIndexer && this.indexerTrainer && this.lightningMode !== 'off') {
      try {
        const trainResult = await this.trainLightningIndexer()
        if (trainResult && !trainResult.skipped) {
          this.logger.info('Lightning Indexer trained during consolidation', {
            retrievals: trainResult.retrievalsTrained,
            lossBefore: trainResult.initialLoss?.toFixed(4),
            lossAfter: trainResult.finalLoss?.toFixed(4),
          })

          // Auto-promotion: switch from shadow to sparsify when ready
          if (this.lightningMode === 'shadow' && this.indexerReadyForPromotion) {
            this.setLightningMode('sparsify')
            this.logger.info('Lightning Indexer auto-promoted to sparsify mode', {
              triples: this.indexerTrainer.totalProcessed,
              steps: this.indexerTrainer.steps,
            })
          }
        }
      } catch (err) {
        this.logger.warn('Lightning Indexer training failed', { error: String(err) })
      }
    }

    return result
  }

  /**
   * Assign every orphaned engram (no cluster_id) to its nearest nucleus
   * by 3D Euclidean distance. Processes in chunks of 5000 to stay
   * memory-friendly. After assignment, recomputes all nucleus centroids
   * from their new member sets.
   */
  private assignOrphansToNearestNucleus(): number {
    const nuclei = this.cortex.listNuclei()
    if (nuclei.length === 0) return 0

    const centroids = nuclei.map(n => ({
      id: n.id,
      x: n.centroidX,
      y: n.centroidY,
      z: n.centroidZ ?? 0,
    }))

    const CHUNK = 5000
    let offset = 0
    let totalAssigned = 0

    while (true) {
      const orphans = this.cortex.listOrphanedPositions(CHUNK, offset)
      if (orphans.length === 0) break

      const byNucleus = new Map<string, string[]>()
      for (const o of orphans) {
        let minDist = Infinity
        let nearest = centroids[0].id
        for (const c of centroids) {
          const dx = o.x - c.x, dy = o.y - c.y, dz = (o.z ?? 0) - c.z
          const d = dx * dx + dy * dy + dz * dz
          if (d < minDist) { minDist = d; nearest = c.id }
        }
        const batch = byNucleus.get(nearest)
        if (batch) batch.push(o.id)
        else byNucleus.set(nearest, [o.id])
      }
      // Assign each batch directly — avoids N×M SQL queries from assignToNucleus
      const tx = (this.cortex as any).db.transaction(() => {
        for (const [nucleusId, ids] of byNucleus) {
          const placeholders = ids.map(() => '?').join(',')
          ;(this.cortex as any).db.prepare(
            `UPDATE engrams SET cluster_id = ? WHERE id IN (${placeholders})`
          ).run(nucleusId, ...ids)
          totalAssigned += ids.length
        }
      })
      tx()
      offset += CHUNK
    }

    this.cortex.recomputeNucleusCentroids()
    return totalAssigned
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

  /**
   * Get query feature keys for read-time sentence selection.
   * Delegates to the decomposer's gate-vector extraction.
   * Returns empty set if decomposer is not available.
   */
  getQueryFeatures(query: string): Set<string> {
    if (!this.decomposer?.isReady()) return new Set()
    return this.decomposer.getQueryFeatures(query)
  }

  renderContext(
    query: string,
    options: KindlingOptions & { tokenBudget?: number },
  ): { entries: Array<{ engramId: string; zoom: string; rendered: string; tokenEstimate: number }>; totalTokens: number } {
    const luminal = this.kindle(null, query, options)
    const budget = options.tokenBudget ?? 2000

    // Pre-compute query features once for all engrams.
    const queryFeatures = this.getQueryFeatures(query)
    const useStructuralLayers = queryFeatures.size > 0

    let totalTokens = 0
    const entries = luminal.engrams.map((e) => {
      const sentences = e.engram.metadata?.sentences as { entries?: Array<{ text: string; features: string[]; tokenCount: number }> } | undefined
      const fieldCoords = e.engram.metadata?.fieldCoords as { r: number; theta: number; z: number } | undefined
      const isSpatial = e.engram.nodeType === 'spatial_feature'

      let rendered: string
      let tokenEstimate: number

      if (useStructuralLayers && sentences?.entries?.length) {
        const perEngramBudget = Math.max(200, Math.floor(budget / luminal.engrams.length))
        const scored = scoreSentencesByOverlap(sentences.entries, queryFeatures)
        const selected: string[] = []
        let tokens = 0
        for (const s of scored) {
          if (tokens + s.tokenCount > perEngramBudget) break
          selected.push(s.text)
          tokens += s.tokenCount
        }
        rendered = selected.join('\n')
        tokenEstimate = tokens
      } else {
        rendered = e.engram.content.slice(0, 500)
        tokenEstimate = Math.ceil(e.engram.content.length / 4)
      }

      if (isSpatial && fieldCoords) {
        const descriptor = `[3D: r=${fieldCoords.r.toFixed(2)} θ=${fieldCoords.theta.toFixed(2)} z=${fieldCoords.z.toFixed(2)}]`
        rendered = `${descriptor} ${rendered}`
        tokenEstimate += 12
      }

      totalTokens += tokenEstimate
      return {
        engramId: e.engram.id,
        zoom: 'full' as const,
        tokenEstimate,
        rendered,
        ...(isSpatial && fieldCoords ? { spatialCoords: fieldCoords } : {}),
      }
    })

    return { entries, totalTokens }
  }

  buildDelegationContext(
    query: string,
    options: KindlingOptions,
  ): { renderedText: string } {
    const luminal = this.kindle(null, query, options)
    const queryFeatures = this.getQueryFeatures(query)
    const useStructuralLayers = queryFeatures.size > 0

    const parts = luminal.engrams.map(e => {
      const sentences = e.engram.metadata?.sentences as { entries?: Array<{ text: string; features: string[]; tokenCount: number }> } | undefined

      if (useStructuralLayers && sentences?.entries?.length) {
        // Delegation context is tight — take top 3 sentences per engram.
        const scored = scoreSentencesByOverlap(sentences.entries, queryFeatures)
        return scored.slice(0, 3).map(s => s.text).join('\n')
      }
      return e.engram.content
    })

    return { renderedText: parts.join('\n\n') }
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

  /** Get the consolidation engine (for sector attention, global attention, etc.). */
  getConsolidationEngine(): ConsolidationEngine {
    return this.consolidationEngine
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
    this.closed = true
    this.cortex.close()
    this.logger.info('Mnemic Field closed')
  }

  /**
   * Ingest a single spatial position as an engram in the mnemic field.
   *
   * Pipeline: tokenize position → gateKnn via TRELLIS.2 vindex → gateEmbed → store.
   * The engram gets (r, θ, z) field coordinates derived from the 3D position,
   * with z stored in metadata for 3D-aware kindling.
   */
  async ingestSpatialPosition(
    x: number,
    y: number,
    z: number,
    options?: {
      /** Tags to attach to the engram. */
      tags?: string[]
      /** Source vindex to use (default: 'trellis2-4b'). */
      source?: string
    },
  ): Promise<{ engramId: string; tokenId: number; fieldCoords: { r: number; theta: number; z: number } } | null> {
    if (!this.vindexEmbedder) {
      this.logger.warn('Cannot ingest spatial position: no vindex embedder configured')
      return null
    }

    const source = options?.source ?? 'trellis2-4b'
    const pos = tokenizePosition(x, y, z)
    const fieldCoords = positionToFieldCoords({ x, y, z })

    // Create a synthetic content string for the spatial position.
    // The gateKnn pipeline will tokenize this and use the spatial tokenizer.
    const content = `spatial_position_${pos.tokenId}`

    // Gate-embed via the vindex (uses the TRELLIS.2 tokenizer internally).
    const embedding = this.vindexEmbedder(content, { source })
    if (!embedding || embedding.length === 0) {
      this.logger.debug?.('Spatial position produced no embedding', { x, y, z, tokenId: pos.tokenId })
      return null
    }

    // Store as a spatial_feature engram with 3D metadata.
    const result = await this.store({
      content,
      nodeType: 'spatial_feature',
      tags: options?.tags ?? ['spatial', '3d'],
      metadata: {
        spatialPosition: { x, y, z },
        tokenId: pos.tokenId,
        normalizedPosition: pos.normalized,
        fieldCoords,
        vindexSource: source,
      },
    })

    if (!result) return null

    this.logger.debug?.('Spatial position ingested', {
      x, y, z,
      tokenId: pos.tokenId,
      engramId: result.id.slice(0, 12),
      r: fieldCoords.r.toFixed(3),
      theta: fieldCoords.theta.toFixed(3),
      fieldZ: fieldCoords.z.toFixed(3),
    })

    return {
      engramId: result.id,
      tokenId: pos.tokenId,
      fieldCoords,
    }
  }

  /**
   * Ingest a grid of spatial positions as engrams.
   *
   * Generates positions within the unit sphere using the 32³ grid,
   * then ingests each one. Useful for seeding the field with 3D content
   * before real 3D assets arrive.
   *
   * @param density — Grid sampling density (1=every position, 2=every other, etc.)
   * @param options — Ingestion options
   * @returns Summary of ingested positions
   */
  async ingestSpatialGrid(
    density: number = 2,
    options?: {
      tags?: string[]
      source?: string
      /** Maximum positions to ingest (default: all generated). */
      limit?: number
    },
  ): Promise<{ generated: number; ingested: number; failed: number; durationMs: number }> {
    const start = Date.now()
    const positions = generateSpatialGrid(density)
    const limit = options?.limit ?? positions.length
    const toIngest = positions.slice(0, limit)

    this.logger.info('Ingesting spatial grid', {
      density,
      generated: positions.length,
      toIngest: toIngest.length,
    })

    let ingested = 0
    let failed = 0

    for (const pos of toIngest) {
      try {
        const result = await this.ingestSpatialPosition(pos.x, pos.y, pos.z, options)
        if (result) {
          ingested++
        } else {
          failed++
          this.logger.debug?.('Spatial position returned null', { x: pos.x, y: pos.y, z: pos.z })
        }
      } catch (err) {
        failed++
        this.logger.debug?.('Spatial position ingestion error', { x: pos.x, y: pos.y, z: pos.z, error: String(err) })
      }

      // Yield every 10 positions to keep the event loop responsive
      if ((ingested + failed) % 10 === 0) {
        await new Promise(resolve => setImmediate(resolve))
      }
    }

    const durationMs = Date.now() - start
    this.logger.info('Spatial grid ingestion complete', {
      generated: positions.length,
      ingested,
      failed,
      durationMs,
    })

    return { generated: positions.length, ingested, failed, durationMs }
  }

  /**
   * Parallel backfill using worker threads.
   *
   * Spawns `workerCount` workers, each loading its own vindex handle
   * (mmap shared via OS page cache). Divides engrams into batches and
   * distributes across workers. Workers embed engrams in parallel and
   * transfer Float32Arrays back via zero-copy ArrayBuffer transfer.
   *
   * Bulk-writes embeddings to DB after each batch completes.
   * Returns total embedded count and elapsed time.
   */
  async backfillEmbeddingsParallel(
    options?: {
      /** Number of worker threads (default 4). */
      workerCount?: number
      /** Maximum engrams to backfill (default: all). */
      limit?: number
      /** Batch size per worker message (default 200). */
      batchSize?: number
      /** Vindex path for workers to load. */
      vindexPath?: string
    },
  ): Promise<{ embedded: number; durationMs: number }> {
    if (this.embeddingBackend !== 'vindex' && !this.vindexEmbedder) {
      // Fall back to serial backfill if vindex isn't configured
      return this.backfillEmbeddings(options?.limit ?? 1000).then(r => ({
        embedded: r.embedded,
        durationMs: Date.now() - startMs,
      }))
    }

    const workerCount = options?.workerCount ?? 4
    const batchSize = options?.batchSize ?? 200
    const vindexPath = options?.vindexPath ??
      (this.vindexEmbedder as any)?.handle?.path
    if (!vindexPath) {
      throw new Error('vindexPath required for parallel backfill')
    }

    const startMs = Date.now()

    // Initialize pool lazily
    if (!this.backfillPool) {
      this.backfillPool = new BackfillWorkerPool(
        this.logger, vindexPath, workerCount,
      )
      await this.backfillPool.initialize()
    }

    const pool = this.backfillPool
    let totalEmbedded = 0

    // Process engrams in batches until done
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const missing = this.cortex.getEngramsNeedingBackfill(
        options?.limit ? Math.min(batchSize * workerCount, options.limit - totalEmbedded) : batchSize * workerCount,
      )
      if (missing.length === 0) break

      // Divide into per-worker chunks
      const chunks: Array<Array<{ id: string; content: string }>> = []
      const chunkSize = Math.ceil(missing.length / workerCount)
      for (let i = 0; i < workerCount; i++) {
        const chunk = missing.slice(i * chunkSize, (i + 1) * chunkSize)
        if (chunk.length > 0) chunks.push(chunk)
      }

      // Dispatch to workers and collect results
      const results = await pool.processBatch(chunks)

      // Bulk write embeddings to DB
      let batchEmbedded = 0
      for (const { id, buffer } of results) {
        const embedding = new Float32Array(buffer)
        this.cortex.updateEngram(id, { embedding })
        batchEmbedded++
      }
      totalEmbedded += batchEmbedded

      this.logger.info('Parallel backfill batch complete', {
        batchSize: missing.length,
        embedded: batchEmbedded,
        totalSoFar: totalEmbedded,
        remaining: this.cortex.countMissingEmbeddings(),
      })

      // Yield to event loop between batches
      await new Promise<void>(resolve => setImmediate(resolve))
    }

    const durationMs = Date.now() - startMs
    this.logger.info('Parallel backfill complete', {
      embedded: totalEmbedded,
      durationMs,
    })

    return { embedded: totalEmbedded, durationMs }
  }
}

// BackfillWorkerPool — manages persistent worker threads for parallel
// gate-vector embedding. Workers load the vindex once and process
// multiple batches.

interface BackfillBatchResult {
  id: string
  buffer: ArrayBuffer
}

class BackfillWorkerPool {
  private workers: Worker[] = []
  private ready = new Set<number>()
  private logger: ILogger
  private vindexPath: string
  private workerCount: number
  private nextBatchId = 0

  constructor(logger: ILogger, vindexPath: string, workerCount: number) {
    this.logger = logger.child?.('backfill-pool') ?? logger
    this.vindexPath = vindexPath
    this.workerCount = workerCount
  }

  async initialize(): Promise<void> {
    // Worker path is package-relative (co-located with this module), so it
    // resolves in both tsx dev and compiled dist/ builds. cassi-larql native
    // addon is a peer dep provided by the host at the package's node_modules.
    const workerPath = new URL('./backfill-worker.ts', import.meta.url)

    const readyPromises: Promise<void>[] = []

    for (let i = 0; i < this.workerCount; i++) {
      // Pass tsx/esm loader so the worker can import TypeScript modules.
      // The worker inherits the parent's tsx runtime if available.
      const worker = new Worker(workerPath, {
        workerData: { vindexPath: this.vindexPath },
        execArgv: ['--import', 'tsx/esm'],
      })

      const ready = new Promise<void>((resolve) => {
        worker.on('message', (msg: { type: string }) => {
          if (msg.type === 'ready') {
            this.ready.add(i)
            resolve()
          }
        })
      })

      worker.on('error', (err) => {
        this.logger.error('Backfill worker error', { worker: i, error: String(err) })
      })

      this.workers.push(worker)
      readyPromises.push(ready)
    }

    await Promise.all(readyPromises)
    this.logger.info('Backfill worker pool ready', { workers: this.ready.size })
  }

  /**
   * Process engram chunks across all workers in parallel.
   * Returns flattened results from all workers.
   */
  async processBatch(
    chunks: Array<Array<{ id: string; content: string }>>,
  ): Promise<BackfillBatchResult[]> {
    const batchPromises: Promise<BackfillBatchResult[]>[] = []

    for (let i = 0; i < chunks.length; i++) {
      const worker = this.workers[i]
      if (!worker) continue

      const batchId = this.nextBatchId++
      const chunk = chunks[i]

      const promise = new Promise<BackfillBatchResult[]>((resolve, reject) => {
        const handler = (msg: { type: string; batchId: number; ids?: string[]; buffers?: ArrayBuffer[]; message?: string }) => {
          if (msg.type === 'result' && msg.batchId === batchId) {
            worker.removeListener('message', handler)
            const results: BackfillBatchResult[] = []
            for (let j = 0; j < (msg.ids?.length ?? 0); j++) {
              results.push({ id: msg.ids![j], buffer: msg.buffers![j] })
            }
            resolve(results)
          } else if (msg.type === 'error') {
            worker.removeListener('message', handler)
            reject(new Error(msg.message))
          }
        }
        worker.on('message', handler)
        worker.postMessage({ type: 'batch', batchId, batch: chunk })
      })

      batchPromises.push(promise)
    }

    const results = await Promise.all(batchPromises)
    return results.flat()
  }

  /** Terminate all workers. */
  async shutdown(): Promise<void> {
    for (const w of this.workers) {
      await w.terminate()
    }
    this.workers = []
    this.ready.clear()
  }
}

/**
 * Spherical linear interpolation (slerp) between two unit-norm gate embeddings.
 *
 * Both vectors live on the unit hypersphere S^{d-1}. Euclidean interpolation
 * (lerp) would move off the sphere; slerp stays on the geodesic. When two
 * engrams merge, we slerp their embeddings so the resulting engram's position
 * reflects both contributions.
 *
 * t ∈ [0,1]: 0 = pure a, 1 = pure b, 0.5 = midpoint.
 * Uses the blog post's formula: sin((1-t)·ω)/sin(ω) · a + sin(t·ω)/sin(ω) · b
 * where ω = arccos(a·b) is the geodesic angle between them.
 */
export function slerpEmbedding(a: Float32Array, b: Float32Array, t: number): Float32Array {
  if (a.length !== b.length) throw new Error('slerpEmbedding: dimension mismatch')
  const n = a.length

  // Compute dot product and clamp for numerical safety
  let dot = 0
  for (let i = 0; i < n; i++) dot += a[i] * b[i]
  dot = Math.max(-1, Math.min(1, dot))

  const omega = Math.acos(dot) // geodesic angle
  if (omega < 0.0001) return new Float32Array(a) // nearly identical — just copy

  const sinOmega = Math.sin(omega)
  const wA = Math.sin((1 - t) * omega) / sinOmega
  const wB = Math.sin(t * omega) / sinOmega

  const result = new Float32Array(n)
  for (let i = 0; i < n; i++) {
    result[i] = wA * a[i] + wB * b[i]
  }
  return result
}

export { KnowledgeField } from './knowledge/knowledge-field.js'
