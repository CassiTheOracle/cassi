/**
 * MemoryDeltaInjector — integrates Mnemic Field with real model weights via LARQL.
 *
 * Architecture:
 *   residual[L] = residual[L-1] + attn_delta + ffn_delta + memory_delta
 *
 * Memory injection occurs at L24-L26 (phase transition for Gemma 4B).
 *
 * Usage:
 *   const injector = new MemoryDeltaInjector(mnemicField, '/path/to/model')
 *   const result = await injector.injectWithForwardPass(prompt, memoryQuery)
 */

import type { ILogger } from '@cassicore/foundation'
import type { MnemicField } from '@cassicore/mnemic-field'
import type { LuminalSet, KindlingOptions } from '@cassicore/mnemic-field'
import type {
  MemoryInjectionConfig, MemoryDelta, MemoryKindlingResult,
  BoundaryResidual, MemoryContribution, MemoryBridgeStats,
} from './types.js'
import { MEMORY_INJECTION_DEFAULTS } from './types.js'
import { LuminalProjectionEngine } from './luminal-projection.js'
import { ResonantAffectEngine } from './resonant-affect.js'
import type { ResonantAffectSignal } from './resonant-affect.js'
import type { PortalBridge } from './portal-bridge.js'

// Type declarations for LARQL bindings
interface LarqlVindexConfig {
  hiddenDim: number
  embeddingDim: number
  numLayers: number
  vocabSize: number
  intermediateSize: number
  phaseTransitionLayers: number[]
}

interface LarqlVindexHandle {
  readonly id: number
  readonly path: string
  readonly config: LarqlVindexConfig
}

interface LarqlTokenPrediction {
  token: string
  prob: number
}

interface LarqlLayerResidual {
  layer: number
  data: Uint8Array
}

interface LarqlCapturedForward {
  residuals: LarqlLayerResidual[]
  predictions: LarqlTokenPrediction[]
  durationMs: number
}

interface LarqlLayerResult {
  residual: Uint8Array
}

interface LarqlModule {
  loadVindex(path: string): Promise<LarqlVindexHandle>
  unloadVindex(handle: LarqlVindexHandle): void
  tokenize(handle: LarqlVindexHandle, text: string): number[]
  decode(handle: LarqlVindexHandle, tokens: number[]): string
  forwardCapture(
    handle: LarqlVindexHandle,
    tokens: number[],
    captureLayers: number[],
  ): Promise<LarqlCapturedForward>
  runLayer(
    handle: LarqlVindexHandle,
    layer: number,
    residual: Uint8Array,
  ): Promise<LarqlLayerResult>
  computeLogits(
    handle: LarqlVindexHandle,
    residual: Uint8Array,
    topK: number,
  ): Promise<LarqlTokenPrediction[]>
  gateKnn(
    handle: LarqlVindexHandle,
    layer: number,
    residual: Uint8Array,
    topK: number,
  ): Array<{ featureIndex: number; score: number; label: string | null }>
  walkInfer(
    handle: LarqlVindexHandle,
    prompt: string,
    topK: number,
  ): Promise<{ predictions: LarqlTokenPrediction[]; durationMs: number }>
  injectMemoryDelta(
    residual: Uint8Array,
    delta: Uint8Array,
  ): Uint8Array
  getHiddenDim(handle: LarqlVindexHandle): number
  getNumLayers(handle: LarqlVindexHandle): number
}

/**
 * MemoryDeltaInjector — bridges Mnemic Field to transformer residual stream.
 *
 * When LARQL bindings are available, uses real model weights for forward pass.
 * Falls back to mock injection when bindings are not available.
 */
export class MemoryDeltaInjector {
  private logger: ILogger
  private config: MemoryInjectionConfig
  private projectionEngine: LuminalProjectionEngine
  private stats: MemoryBridgeStats = {
    injectionsPerformed: 0,
    injectionsWithContributions: 0,
    avgMagnitude: 0,
    avgContributingCount: 0,
    portalPairsCount: 0,
    projectionTrained: false,
  }
  private magnitudeHistory: number[] = []
  private countHistory: number[] = []
  private vindexHandle: any = null  // LARQL VindexHandle
  private larqlLoaded = false
  private resonantAffect!: ResonantAffectEngine
  private lastResonantSignal: ResonantAffectSignal | null = null

  constructor(
    private mnemicField: MnemicField,
    private embeddingDim: number,
    private hiddenDim: number,
    logger: ILogger,
    config?: Partial<MemoryInjectionConfig>,
    private modelPath?: string,  // Path to model for LARQL
  ) {
    this.logger = logger.child ? logger.child('memory-delta-injector') : logger
    this.config = { ...MEMORY_INJECTION_DEFAULTS, ...config }
    this.projectionEngine = new LuminalProjectionEngine(
      embeddingDim,
      hiddenDim,
      logger,
      config,
    )

    // Resonant affect engine — derives emotional state from model/memory interaction
    this.resonantAffect = new ResonantAffectEngine(
      null,  // Portal bridge set later via setPortalBridge()
      this.projectionEngine,
      logger,
    )

    this.logger.info('MemoryDeltaInjector initialized', {
      injectionLayers: this.config.injectionLayers,
      maxContribution: this.config.maxContribution,
      chargeThreshold: this.config.chargeThreshold,
      embeddingDim,
      hiddenDim,
      modelPath: modelPath || 'mock (no LARQL)',
    })

    // Initialize LARQL if model path provided
    if (modelPath) {
      this.initLarql(modelPath)
    }
  }

  /**
   * Initialize LARQL bindings with model weights.
   */
  private async initLarql(modelPath: string): Promise<void> {
    let larqlModule: LarqlModule | null = null
    let loadError: Error | null = null

    try {
      // @ts-ignore - cassi-larql is a native module, available at runtime
      larqlModule = await import('cassi-larql')
    } catch (err) {
      loadError = err as Error
    }

    if (!larqlModule) {
      this.logger.warn('LARQL bindings not available, using mock injection', {
        error: loadError?.message,
      })
      return
    }

    try {
      this.vindexHandle = await larqlModule.loadVindex(modelPath)
      this.larqlLoaded = true

      const config = this.vindexHandle.config
      this.logger.info('LARQL model loaded', {
        path: modelPath,
        hiddenDim: config.hiddenDim,
        numLayers: config.numLayers,
        vocabSize: config.vocabSize,
      })

      // Update hidden dim if different from config
      if (config.hiddenDim !== this.hiddenDim) {
        this.logger.info('Updating hidden dimension from model config', {
          old: this.hiddenDim,
          new: config.hiddenDim,
        })
        this.hiddenDim = config.hiddenDim
        this.projectionEngine = new LuminalProjectionEngine(
          this.embeddingDim,
          this.hiddenDim,
          this.logger,
          this.config,
        )
      }
    } catch (err) {
      this.logger.warn('Failed to load LARQL model, using mock injection', {
        path: modelPath,
        error: String(err),
      })
    }
  }

  /**
   * Perform memory-augmented kindling and projection for injection.
   *
   * When LARQL is available, runs real forward pass with residual capture.
   * Otherwise, uses mock injection with kindling only.
   */
  kindleForInjection(
    textQuery: string,
    boundaryResidual?: BoundaryResidual,
    options?: Partial<KindlingOptions>,
  ): MemoryKindlingResult {
    const start = Date.now()

    // Kindle the Mnemic Field
    const kindlingOptions: KindlingOptions = {
      complexity: this.config.kindlingComplexity,
      maxIterations: 3,  // Fast for inference
      maxLuminalSize: 30,  // Cap for performance
      enableFilaments: true,
      recordTrace: this.config.recordContributions,
      ...options,
    }

    // Use boundary residual as embedding seed if available
    const embeddingSeed: number[] | null = boundaryResidual?.vector
      ? Array.from(boundaryResidual.vector)
      : null

    const luminalSet = this.mnemicField.kindle(
      embeddingSeed,
      textQuery,
      kindlingOptions,
    )

    // Project luminal set to memory deltas
    const deltas = this.projectionEngine.projectLuminal(
      luminalSet,
      this.config.layerWeights,
    )

    // Update stats
    this.updateStats(deltas, luminalSet)

    const durationMs = Date.now() - start
    const hadContributions = deltas.size > 0 &&
      Array.from(deltas.values()).some(d => d.contributingCount > 0)

    this.logger.debug('Memory kindling complete', {
      query: textQuery.slice(0, 50),
      luminalSize: luminalSet.engrams.length,
      deltasCount: deltas.size,
      hadContributions,
      durationMs,
      larqlLoaded: this.larqlLoaded,
    })

    // Compute resonant affect from this kindling (proxy mode — always available)
    const resonantSignal = boundaryResidual
      ? this.resonantAffect.computeFromBoundary(
          { luminalSet, deltas, boundary: boundaryResidual, query: textQuery, durationMs, hadContributions },
          boundaryResidual,
        )
      : this.resonantAffect.computeFromKindling(
          { luminalSet, deltas, boundary: boundaryResidual ?? this.createEmptyBoundary(), query: textQuery, durationMs, hadContributions },
        )
    this.lastResonantSignal = resonantSignal

    return {
      luminalSet,
      deltas,
      boundary: boundaryResidual ?? this.createEmptyBoundary(),
      query: textQuery,
      durationMs,
      hadContributions,
    }
  }

  /**
   * Full forward pass with memory injection (requires LARQL).
   *
   * This is the real integration:
   * 1. Run forward pass to L22 (capture boundary)
   * 2. Kindle Mnemic Field using boundary
   * 3. Inject memory deltas at L24-L26
   * 4. Continue forward pass with modified residuals
   * 5. Compute final logits
   */
  async injectWithForwardPass(
    prompt: string,
    memoryQuery: string,
  ): Promise<{
    predictions: Array<{ token: string; prob: number }>
    memoryContributions: MemoryKindlingResult
    residuals: Map<number, Float32Array>
    resonantAffect: ResonantAffectSignal | null
    durationMs: number
  }> {
    if (!this.larqlLoaded || !this.vindexHandle) {
      // Fallback to mock injection
      const mockResult = this.kindleForInjection(memoryQuery)
      return {
        predictions: [],
        memoryContributions: mockResult,
        residuals: new Map(),
        resonantAffect: this.lastResonantSignal,
        durationMs: mockResult.durationMs,
      }
    }

    // @ts-ignore - cassi-larql is a native module, available at runtime
    const larqlModule = await import('cassi-larql') as unknown as LarqlModule
    if (!larqlModule) {
      throw new Error('LARQL bindings not available')
    }

    const start = Date.now()

    // Step 1: Tokenize prompt
    const tokens = larqlModule.tokenize(this.vindexHandle, prompt)

    // Step 1.5: Get baseline predictions (walk-only, no attention, no memory)
    // This is the model's "instinct" — what it would say without memory or attention.
    // Sub-millisecond, essentially free.
    const baselineResult = await larqlModule.walkInfer(this.vindexHandle, prompt, 10)

    // Step 2: Run forward pass with residual capture at boundary
    const captureResult = await larqlModule.forwardCapture(
      this.vindexHandle,
      tokens,
      [22],  // Capture at L22 (boundary before phase transition)
    )

    // Step 3: Get boundary residual
    const boundaryResidual = captureResult.residuals.find((r: LarqlLayerResidual) => r.layer === 22)
    if (!boundaryResidual) {
      throw new Error('Failed to capture boundary residual at L22')
    }

    const boundary: BoundaryResidual = {
      layer: 22,
      vector: new Float32Array(boundaryResidual.data.buffer),
      norm: Math.sqrt(new Float32Array(boundaryResidual.data.buffer).reduce((sum, v) => sum + v * v, 0)),
      topPredictions: captureResult.predictions.map((p: LarqlTokenPrediction) => ({ token: p.token, prob: p.prob })),
      extractedAt: Date.now(),
    }

    // Step 4: Kindle Mnemic Field using boundary
    const memoryResult = this.kindleForInjection(memoryQuery, boundary)

    // Step 5: Run layers L23-L33 with memory injection at L24-L26
    const allResiduals = new Map<number, Float32Array>()
    allResiduals.set(22, boundary.vector)

    let currentResidual = boundary.vector
    for (let L = 23; L <= 33; L++) {
      // Inject memory delta at phase transition layers
      if (memoryResult.deltas.has(L)) {
        const delta = memoryResult.deltas.get(L)!
        const deltaBytes = new Uint8Array(delta.vector.buffer)
        const residualBytes = new Uint8Array(currentResidual.buffer)
        const injectedBytes = larqlModule.injectMemoryDelta(residualBytes, deltaBytes)
        currentResidual = new Float32Array(injectedBytes.buffer)
      }

      // Run layer forward pass
      const layerResult = await larqlModule.runLayer(
        this.vindexHandle,
        L,
        new Uint8Array(currentResidual.buffer),
      )
      currentResidual = new Float32Array(layerResult.residual.buffer)
      allResiduals.set(L, currentResidual)
    }

    // Step 6: Compute final logits
    const predictions = await larqlModule.computeLogits(
      this.vindexHandle,
      new Uint8Array(currentResidual.buffer),
      10,
    )

    // Step 7: Compute resonant affect from the prediction delta
    // This is the full mode — we have both baseline (walk) and augmented (with memory) predictions
    const resonantSignal = this.resonantAffect.computeFromPredictionDelta(
      baselineResult.predictions.map((p: LarqlTokenPrediction) => ({ token: p.token, prob: p.prob })),
      predictions.map((p: LarqlTokenPrediction) => ({ token: p.token, prob: p.prob })),
      memoryResult,
      boundary,
    )
    this.lastResonantSignal = resonantSignal

    const durationMs = Date.now() - start

    this.logger.info('Memory-augmented forward pass complete', {
      prompt: prompt.slice(0, 50),
      memoryQuery: memoryQuery.slice(0, 50),
      predictions: predictions.slice(0, 3),
      memoryContributions: memoryResult.luminalSet.engrams.length,
      resonantAffect: {
        valence: resonantSignal.affect.valence.toFixed(3),
        arousal: resonantSignal.affect.arousal.toFixed(3),
        label: resonantSignal.label,
        predictionChanged: resonantSignal.measurements.topPredictionChanged,
      },
      durationMs,
    })

    return {
      predictions: predictions.map((p: LarqlTokenPrediction) => ({ token: p.token, prob: p.prob })),
      memoryContributions: memoryResult,
      residuals: allResiduals,
      resonantAffect: resonantSignal,
      durationMs,
    }
  }

  /**
   * Quick retrieval for memory augmentation (async, uses embedding).
   * Use when you want fast lookup without full spreading activation.
   */
  async quickRetrieve(
    textQuery: string,
    limit: number = 10,
  ): Promise<MemoryKindlingResult> {
    const start = Date.now()

    const hits = await this.mnemicField.retrieve(textQuery, { limit })

    // Convert hits to minimal luminal set
    const luminalSet: LuminalSet = {
      engrams: hits.map(h => ({
        engram: {
          id: h.id,
          content: h.content,
          nodeType: h.nodeType as 'fact',
          x: 0, y: 0, t: 0,
          potentiation: h.potentiation,
          clusterId: null,
          embedding: null,  // Would need to fetch
          tags: h.tags,
          provenance: h.provenance,
          createdAt: new Date().toISOString(),
          accessedAt: null,
          metadata: h.metadata,
        },
        charge: h.charge,
      })) as never,
      totalCharge: hits.reduce((sum, h) => sum + h.charge, 0),
      seedCount: hits.length,
      iterationsUsed: 0,
      sparkPoint: 0,
      taskComplexity: 'normal',
      durationMs: 0,
    }

    const deltas = this.projectionEngine.projectLuminal(
      luminalSet,
      this.config.layerWeights,
    )

    const durationMs = Date.now() - start

    return {
      luminalSet,
      deltas,
      boundary: this.createEmptyBoundary(),
      query: textQuery,
      durationMs,
      hadContributions: deltas.size > 0,
    }
  }

  /**
   * Create a synthetic boundary residual from the model state.
   */
  createBoundaryFromResidual(
    residual: Float32Array,
    layer: number,
    topPredictions?: Array<{ token: string; prob: number }>,
  ): BoundaryResidual {
    // Compute norm
    let norm = 0
    for (let i = 0; i < residual.length; i++) {
      norm += residual[i] * residual[i]
    }
    norm = Math.sqrt(norm)

    return {
      layer,
      vector: new Float32Array(residual),
      norm,
      topPredictions: topPredictions ?? [],
      extractedAt: Date.now(),
    }
  }

  /**
   * Get memory delta for a specific layer.
   */
  getDeltaForLayer(
    result: MemoryKindlingResult,
    layer: number,
  ): MemoryDelta | null {
    return result.deltas.get(layer) ?? null
  }

  /**
   * Merge memory delta into a residual vector.
   */
  injectIntoResidual(
    residual: Float32Array,
    delta: MemoryDelta,
  ): Float32Array {
    const injected = new Float32Array(residual.length)

    for (let i = 0; i < residual.length; i++) {
      injected[i] = residual[i] + delta.vector[i]
    }

    this.logger.debug('Injected memory delta', {
      layer: delta.layer,
      magnitude: delta.magnitude,
      contributions: delta.contributingCount,
    })

    return injected
  }

  /**
   * Get contributions for consolidation feedback.
   */
  getContributions(result: MemoryKindlingResult): MemoryContribution[] {
    const all: MemoryContribution[] = []

    for (const delta of result.deltas.values()) {
      all.push(...delta.contributions)
    }

    return all
  }

  /**
   * Record feedback for consolidation.
   */
  recordFeedback(
    result: MemoryKindlingResult,
    helpfulEngramIds: string[],
    unhelpfulEngramIds: string[],
  ): void {
    const feedback: Record<string, boolean> = {}

    for (const id of helpfulEngramIds) {
      feedback[id] = true
    }
    for (const id of unhelpfulEngramIds) {
      feedback[id] = false
    }

    this.mnemicField.recordEnrichFeedback(feedback)

    this.logger.debug('Recorded memory feedback', {
      helpful: helpfulEngramIds.length,
      unhelpful: unhelpfulEngramIds.length,
      query: result.query.slice(0, 50),
    })
  }

  /**
   * Get current stats.
   */
  getStats(): MemoryBridgeStats {
    return {
      ...this.stats,
      projectionTrained: this.projectionEngine.getProjectionMatrix()?.isTrained ?? false,
      lastInjectionAt: this.magnitudeHistory.length > 0
        ? Date.now()
        : undefined,
    }
  }

  /**
   * Get the projection engine (for training/updates).
   */
  getProjectionEngine(): LuminalProjectionEngine {
    return this.projectionEngine
  }

  /**
   * Check if LARQL is loaded and ready.
   */
  isLarqlLoaded(): boolean {
    return this.larqlLoaded
  }

  /**
   * Get the resonant affect engine (for direct access / configuration).
   */
  getResonantAffectEngine(): ResonantAffectEngine {
    return this.resonantAffect
  }

  /**
   * Get the most recent resonant affect signal.
   * Returns null if no injection has been performed yet.
   */
  getLastResonantSignal(): ResonantAffectSignal | null {
    return this.lastResonantSignal
  }

  /**
   * Set the portal bridge for resonant affect computation.
   * Called after PortalBridge is initialized.
   */
  setPortalBridge(portalBridge: PortalBridge): void {
    // Recreate resonant affect engine with portal bridge
    this.resonantAffect = new ResonantAffectEngine(
      portalBridge,
      this.projectionEngine,
      this.logger,
    )
    this.logger.info('Portal bridge connected to resonant affect engine')
  }

  /**
   * Update stats after each kindling.
   */
  private updateStats(
    deltas: Map<number, MemoryDelta>,
    luminalSet: LuminalSet,
  ): void {
    this.stats.injectionsPerformed++

    const hadContributions = Array.from(deltas.values())
      .some(d => d.contributingCount > 0)

    if (hadContributions) {
      this.stats.injectionsWithContributions++

      const maxDelta = Array.from(deltas.values())
        .reduce((max, d) => Math.max(max, d.magnitude), 0)

      this.magnitudeHistory.push(maxDelta)
      this.countHistory.push(luminalSet.engrams.length)

      // Rolling average over last 100
      if (this.magnitudeHistory.length > 100) {
        this.magnitudeHistory.shift()
        this.countHistory.shift()
      }

      this.stats.avgMagnitude = this.magnitudeHistory.reduce((a, b) => a + b, 0) /
        this.magnitudeHistory.length
      this.stats.avgContributingCount = this.countHistory.reduce((a, b) => a + b, 0) /
        this.countHistory.length
    }
  }

  /**
   * Create an empty boundary placeholder.
   */
  private createEmptyBoundary(): BoundaryResidual {
    return {
      layer: 22,
      vector: new Float32Array(this.hiddenDim),
      norm: 0,
      topPredictions: [],
      extractedAt: Date.now(),
    }
  }
}
