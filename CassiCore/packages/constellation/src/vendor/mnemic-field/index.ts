/**
 * VENDORED TYPE STUB — mirrors `mnemic-field/index.js` (CassiCore) `MnemicField` type surface.
 * Used by constellation (pipeline, meditation) and the vendored runtime. The full runtime
 * class lives in the daemon; only the used method surface is declared here.
 */
import type {
  Engram,
  EngramCreate,
  EngramUpdate,
  MnemicSynapse,
  SynapseCreate,
  SpikeCreate,
  ActivationSpike,
  MnemicRetrievalHit,
  EngramSearchResult,
  FieldStats,
  Nucleus,
  TensionPair,
} from './types.js'
import type { Cortex } from './cortex.js'

export interface ConsolidationResult {
  potentiationUpdates: number
  positionDrifts: number
  centripetalDrifts: number
  angularDrifts: number
  nucleiDetected: number
  abstractionsCreated: number
  spikesPruned: number
  forwardTracesPruned: number
  contrastiveFeedbackDrifts: number
  durationMs: number
  [key: string]: unknown
}

export interface ConsolidationOptions {
  skipRadiance?: boolean
  skipDrift?: boolean
  skipCentripetalDrift?: boolean
  skipAngularDrift?: boolean
  skipNuclei?: boolean
  skipAbstractions?: boolean
  skipPruning?: boolean
  skipForwardTracePrune?: boolean
  skipGradients?: boolean
  skipDreaming?: boolean
  skipContrastiveFeedback?: boolean
  skipDistinctiveness?: boolean
  [key: string]: unknown
}

export type {
  Engram, EngramCreate, EngramUpdate, MnemicSynapse, SynapseCreate, SpikeCreate,
  ActivationSpike, MnemicRetrievalHit, EngramSearchResult, FieldStats, Nucleus,
  TensionPair,
}

export interface MnemicField {
  spike(input: SpikeCreate): ActivationSpike
  retrieve(query: string, options?: Record<string, unknown>): Promise<MnemicRetrievalHit[]>
  store(input: EngramCreate): Engram
  update(id: string, update: EngramUpdate): Engram | null
  connect(input: SynapseCreate): MnemicSynapse
  getCortex(): Cortex
  list(limit?: number): Engram[]
  searchText(query: string, limit?: number): EngramSearchResult[]
  stats(): FieldStats
  listNuclei(): Nucleus[]
  listAbstractions(limit?: number): Engram[]
  consolidate(options?: ConsolidationOptions): Promise<ConsolidationResult>
  tensions(minPotentiation?: number, limit?: number): TensionPair[]
  backfillEmbeddings(limit?: number): Promise<{ embedded: number; reprojected: number; filamentEmbeddings: number }>
  reprojectAllAsync(umapOptions?: unknown): Promise<number>
  classifyPhrase(text: string, prototypeSet: Record<string, unknown>, threshold?: number): Promise<{ label: string | null; score: number }>
  checkExpertLifecycle(): { dormant: unknown[]; archived: unknown[]; hot: unknown[] }
  findExpertEngrams(opts?: { limit?: number; [key: string]: unknown }): Engram[]
  getEngramsByIdPrefix(prefix: string): Engram[]
  get(id: string): Engram | null
  delete(id: string): void
  bulkUpdateSynapseWeights(updates: Array<Record<string, unknown>>): number
  getTypedSynapses(branchId: string, edgeType: string, direction: string): MnemicSynapse[]
  recordEnrichFeedback(feedback: Record<string, unknown>): boolean
  [key: string]: unknown
}
