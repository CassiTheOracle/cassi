import Database from 'better-sqlite3'
import fs from 'node:fs'
import path from 'node:path'
import type { ILogger } from '../../../types/interfaces.js'
import { getDataDir } from '../../utils/paths.js'
import { Cortex } from './cortex.js'
import { KindlingEngine } from './kindling.js'
import { ConsolidationEngine } from './consolidation.js'
import type { ConsolidationResult, ConsolidationOptions } from './consolidation.js'
import { projectTo2D, projectSingle, computePCAComponents } from './pca.js'
import type {
  Engram, EngramCreate, EngramUpdate,
  MnemicSynapse, SynapseCreate,
  ActivationSpike, SpikeCreate,
  Nucleus, NucleusCreate,
  SpatialQuery, EngramSearchResult, TensionPair, TensionReport, FieldStats,
  TaskComplexity, LuminalSet, KindlingOptions, SpikeOutcome,
} from './types.js'
import { SPARK_POINT_DEFAULTS, POTENTIATION_DEFAULTS } from './types.js'

export { Cortex } from './cortex.js'
export { KindlingEngine } from './kindling.js'
export { ConsolidationEngine } from './consolidation.js'
export type { ConsolidationResult, ConsolidationOptions } from './consolidation.js'
export { projectTo2D, projectSingle, computePCAComponents } from './pca.js'
export type {
  Engram, EngramCreate, EngramUpdate,
  MnemicSynapse, SynapseCreate,
  ActivationSpike, SpikeCreate,
  Nucleus, NucleusCreate,
  SpatialQuery, EngramSearchResult, TensionPair, TensionReport, FieldStats,
  TaskComplexity, LuminalSet, KindlingOptions, ChargedEngram,
} from './types.js'
export {
  ENGRAM_TYPES, SYNAPSE_TYPES, SYNAPSE_PROPAGATION,
  POTENTIATION_DEFAULTS, SPARK_POINT_DEFAULTS, KINDLING_DEFAULTS,
} from './types.js'

interface PCAState {
  mean: number[]
  pc1: number[]
  pc2: number[]
}

export class MnemicField {
  private cortex: Cortex
  private kindlingEngine: KindlingEngine
  private consolidationEngine: ConsolidationEngine
  private logger: ILogger
  private pcaState: PCAState | null = null

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

    this.cortex = new Cortex(db, logger)
    this.kindlingEngine = new KindlingEngine(this.cortex, logger)
    this.consolidationEngine = new ConsolidationEngine(this.cortex, logger)
    this.logger.info('Mnemic Field initialized')
  }

  /**
   * Store a new engram. If embedding is provided but x/y are not,
   * computes XY from PCA against existing field topology.
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

    return this.cortex.createEngram({ ...input, x, y })
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

  /**
   * Compute spike-based importance for an engram (ACT-R base-level equation).
   */
  computeSpikeImportance(engramId: string): number {
    const spikes = this.cortex.getSpikes(engramId, 200)
    if (spikes.length === 0) return 0

    const now = Date.now()
    const d = POTENTIATION_DEFAULTS.decayRate
    let sum = 0

    for (const spike of spikes) {
      const elapsed = Math.max(1, (now - spike.timestamp) / 1000)
      sum += spike.magnitude * Math.pow(elapsed, -d)
    }

    return Math.log1p(sum)
  }

  /**
   * Compute the adaptive α for a specific engram.
   * α determines the balance between spike history and graph structure.
   */
  computeAlpha(engramId: string): number {
    const count = this.cortex.getSpikeCount(engramId)
    const { alphaMin, alphaMax, alphaTau } = POTENTIATION_DEFAULTS
    return alphaMin + (alphaMax - alphaMin) * (1 - Math.exp(-count / alphaTau))
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
   * Rebuild PCA state from all engrams that have embeddings.
   * Call this after bulk imports or periodically during consolidation.
   */
  rebuildPCA(): PCAState | null {
    const engrams = this.cortex.getAllEngrams()
    const vectors = engrams
      .filter(e => e.embedding && e.embedding.length > 0)
      .map(e => Array.from(e.embedding!))

    if (vectors.length < 2) {
      this.pcaState = null
      return null
    }

    this.pcaState = computePCAComponents(vectors)
    this.logger.debug('PCA state rebuilt', { vectorCount: vectors.length })
    return this.pcaState
  }

  /**
   * Project a new vector into XY space using current PCA state.
   * If no PCA state exists, rebuilds from all engrams.
   */
  private projectNewVector(vector: number[]): { x: number; y: number } {
    if (!this.pcaState) {
      this.rebuildPCA()
    }

    if (this.pcaState) {
      return projectSingle(vector, this.pcaState.mean, this.pcaState.pc1, this.pcaState.pc2)
    }

    return { x: 0, y: 0 }
  }

  /**
   * Bulk reproject all engrams using current embeddings.
   * Useful after PCA rebuild or initial migration.
   */
  reprojectAll(): number {
    const engrams = this.cortex.getAllEngrams()
    const withEmbeddings = engrams.filter(e => e.embedding && e.embedding.length > 0)

    if (withEmbeddings.length < 2) return 0

    const vectors = withEmbeddings.map(e => Array.from(e.embedding!))
    const positions = projectTo2D(vectors)

    const updates = withEmbeddings.map((e, i) => ({
      id: e.id,
      x: positions[i].x,
      y: positions[i].y,
    }))

    this.cortex.bulkUpdatePositions(updates)
    this.pcaState = computePCAComponents(vectors)

    this.logger.info('Reprojected all engrams', { count: updates.length })
    return updates.length
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
    return this.kindlingEngine.kindle(embedding, textQuery, options)
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
  }

  /**
   * Run a full consolidation cycle: radiance (potentiation recomputation),
   * co-activation drift, nucleus detection, and spike history pruning.
   */
  consolidate(options?: ConsolidationOptions): ConsolidationResult {
    return this.consolidationEngine.consolidate(options)
  }

  /**
   * Get the underlying Cortex for direct operations.
   * Prefer using MnemicField methods; use this for advanced/batch operations.
   */
  getCortex(): Cortex {
    return this.cortex
  }

  close(): void {
    this.cortex.close()
    this.logger.info('Mnemic Field closed')
  }
}
