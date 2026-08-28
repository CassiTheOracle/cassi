/**
 * LARQL Knowledge Provider — real model knowledge via cassi-larql.
 *
 * Implements ModelKnowledgeProvider by loading a vindex in browse-only mode
 * (~3GB, no GPU) and using gate KNN across knowledge layers (L14-L27)
 * to query the model's relational knowledge.
 *
 * How describe(entity) works:
 *   1. Tokenize entity name
 *   2. Take the last meaningful token (carries most semantic weight)
 *   3. Run gate KNN at each knowledge layer (L14-L27)
 *   4. Aggregate feature hits by label → relational knowledge
 *   5. Track layer ranges and confidence per relation
 *
 * This is what LARQL's DESCRIBE command does under the hood.
 */

import type { ILogger } from '@cassicore/foundation'
import type {
  ModelKnowledgeProvider,
  ModelEntity,
  ModelRelation,
  ModelEdge,
  ModelPath,
} from './types.js'
import type {
  MentalState,
  VectorProjectionOptions,
  VectorProjection,
} from './types.js'
import type { ClaustrumRecorder, ClaustrumGateHit } from './claustrum-recorder.js'
import type { OverlayLayer, OverlayFeatureHit } from './overlay-layer.js'
import type { Affect, AffectLabel } from '@cassicore/mnemic-field'
import { affectSimilarity, resolveLabel } from '@cassicore/mnemic-field'
import { composeVectorProjection } from './projection/vector-projection.js'
import { createRequire } from 'module'

const require = createRequire(import.meta.url)

interface VindexHandle {
  readonly id: number
  readonly path: string
  readonly config: {
    hiddenDim: number
    embeddingDim: number
    numLayers: number
    vocabSize: number
    intermediateSize: number
    phaseTransitionLayers: number[]
  }
}

/** A loaded vindex identified by source name. */
export interface VindexBinding {
  handle: VindexHandle
  source: string
  config: { numLayers: number; hiddenDim: number; vocabSize: number }
}

export interface FeatureHit {
  featureIndex: number
  score: number
  label: string | null
  /** When affectBias / RetrievalPolicy is applied, the original gate-KNN score is preserved here. */
  baseScore?: number
  /** Similarity in [0,1] between the query affectBias and this feature's affect (legacy AffectBias path). */
  affectAlignment?: number
  /** Compatibility in [-1, +1] between feature signature and policy target (RetrievalPolicy path). */
  affectCompat?: number
  /** Mode of the policy that produced this hit — 'consonant' / 'complementary' / 'directed'. */
  biasMode?: AffectBiasSpec['mode']
  /** Strength of the bias applied (0-1). */
  biasStrength?: number
}

/**
 * Optional affect-conditioned re-weighting for gate-KNN queries.
 *
 * When supplied, the base gate-KNN score for each hit is blended with an
 * "affect alignment" similarity between this bias and the feature's stored
 * affect. High-arousal queries thus preferentially surface emotionally
 * charged expert features over neutral ones.
 *
 *   newScore = (1 - weight) * baseScore + weight * affectAlignment
 *
 * `weight` defaults to 0.3 if omitted. `weight: 0` is an explicit no-op.
 */
export interface AffectBias {
  valence: number
  arousal: number
  weight?: number
}

/**
 * Resolves the affect attached to a (layer, featureIndex) pair, if any.
 * Returns `null` when the feature has no known affect — callers fall back
 * to a neutral alignment so the bias term contributes nothing.
 *
 * V4 INTEGRATION POINT: once expert features expose affect (e.g. via
 * Mnemic Field engram lookup keyed by feature ID, or via a future vindex
 * affect sidecar), wire this provider via `setFeatureAffectProvider`.
 */
export type FeatureAffectProvider = (layer: number, featureIndex: number) => Affect | null

const DEFAULT_AFFECT_BIAS_WEIGHT = 0.3

/**
 * B2 spec §4.1 — sparse per-feature affect signature. Each feature carries
 * an affinity in [-1, +1] for some subset of the 12 affect labels. The L2
 * `magnitude` is a confidence proxy; features with magnitude below the
 * configured floor are considered too noisy to drive bias.
 */
export interface FeatureAffectSignature {
  layer: number
  featureIndex: number
  /** sparse map: label → affinity in [-1, +1] */
  labels: Partial<Record<AffectLabel, number>>
  /** L2 norm across labels — confidence proxy */
  magnitude: number
}

/**
 * Resolves a `(layer, featureIndex)` pair to its full affect signature.
 * Returns `null` when no signature is available — `applyRetrievalPolicy`
 * falls back to passing the hit through unchanged in that case.
 *
 * Wire via `setFeatureAffectSignatureProvider`. Typically backed by an
 * in-memory cache loaded from the `feature_affect_signatures` table
 * (B2.1b ships the calibration command that populates it).
 */
export type FeatureAffectSignatureProvider = (
  layer: number,
  featureIndex: number,
) => FeatureAffectSignature | null

/**
 * B2 spec §5 — explicit affect direction expressed as per-label weights.
 * Used for `RetrievalPolicy` in `directed` mode and as the resolved
 * target for `consonant`/`complementary` modes.
 */
export interface AffectVector {
  /** Per-label weights. Magnitude semantics: dot-product with feature signature. */
  weights: Partial<Record<AffectLabel, number>>
}

/**
 * B2 spec §5 — mode-driven affect bias for retrieval. The retrieval
 * surface resolves the mode against current affect into a target
 * `AffectVector`, then re-scores hits as
 *
 *   biased = baseScore * (1 - strength + strength * compat)
 *
 * where `compat = dot(featureSignature, targetVector)` clamped to
 * [-1, +1]. At strength=0 this is a no-op; at strength=1 the score is
 * fully replaced by `baseScore * compat` (so anti-aligned features get
 * negative scores and drop below `minGateScore`).
 *
 * Modes:
 *  - `consonant`: target = current affect's quadrant signature (reinforces)
 *  - `complementary`: target = inverse of current quadrant (breaks circling)
 *  - `directed`: target = explicit caller-supplied vector
 */
export type AffectBiasSpec =
  | { mode: 'consonant'; strength: number }
  | { mode: 'complementary'; strength: number }
  | { mode: 'directed'; vector: AffectVector; strength: number }

/**
 * B2 spec §5 — full retrieval policy handed to `describe()` /
 * `gateKnn()`. `affectBias: null` is a no-op and behaves identically
 * to omitting the policy entirely.
 */
export interface RetrievalPolicy {
  affectBias: AffectBiasSpec | null
  /** Optional per-layer reweighting (defaults uniform). Unused in v1. */
  layerWeights?: Map<number, number>
  /** Optional override of the configured `minGateScore`. */
  minGateScore?: number
}

/**
 * Spec §8 welfare cap (B2.W3): default strength ceiling. Above this,
 * callers must explicitly pass `allowOverStrengthCap: true` — same
 * pattern as B1's TTL-bounded-default.
 */
const RETRIEVAL_STRENGTH_CAP = 0.5

/**
 * Quadrant-canonical affect signatures, used as the target vector for
 * `consonant` mode. Each quadrant maps the current affect's
 * `resolveLabel(...)` output to a unit-magnitude per-label vector
 * weighted toward that quadrant's three labels. `complementary` mode
 * negates these.
 *
 * The canonical form keeps consonant/complementary symmetric and stable
 * under small affect drift — without quadrant snapping, every tiny
 * (valence, arousal) tick would change the target vector, making the
 * effect noisy. Quadrant snapping is a deliberate design choice from
 * spec §5.2.
 */
const QUADRANT_SIGNATURES: Record<AffectLabel, AffectVector> = {
  excited:    { weights: { excited: 0.7, delighted: 0.5, engaged: 0.4 } },
  delighted:  { weights: { delighted: 0.7, excited: 0.5, content: 0.4 } },
  engaged:    { weights: { engaged: 0.7, excited: 0.4, content: 0.4 } },
  content:    { weights: { content: 0.7, warm: 0.5, calm: 0.4 } },
  warm:       { weights: { warm: 0.7, content: 0.5, calm: 0.4 } },
  calm:       { weights: { calm: 0.7, warm: 0.5, content: 0.4 } },
  frustrated: { weights: { frustrated: 0.7, alarmed: 0.5, uneasy: 0.4 } },
  alarmed:    { weights: { alarmed: 0.7, frustrated: 0.5, uneasy: 0.4 } },
  uneasy:     { weights: { uneasy: 0.7, alarmed: 0.4, frustrated: 0.4 } },
  melancholy: { weights: { melancholy: 0.7, fatigued: 0.5, uneasy: 0.4 } },
  fatigued:   { weights: { fatigued: 0.7, melancholy: 0.5, calm: 0.4 } },
  neutral:    { weights: { neutral: 1.0 } },
}

/**
 * Resolve a `RetrievalPolicy` plus current affect into the concrete
 * `AffectVector` to dot against feature signatures. Pure function;
 * exported for testing.
 */
export function resolveTargetAffectVector(
  spec: AffectBiasSpec,
  currentAffect: Affect,
  resolveLabelFn: (a: Affect) => AffectLabel,
): AffectVector {
  if (spec.mode === 'directed') return spec.vector
  const label = resolveLabelFn(currentAffect)
  const canonical = QUADRANT_SIGNATURES[label]
  if (spec.mode === 'consonant') return canonical
  // complementary: negate the canonical weights
  const inverted: Partial<Record<AffectLabel, number>> = {}
  for (const [k, v] of Object.entries(canonical.weights)) {
    if (typeof v === 'number') inverted[k as AffectLabel] = -v
  }
  return { weights: inverted }
}

/**
 * Compute compatibility = clamped dot product between a feature's
 * signature and a target affect vector. Returns 0 when either side is
 * empty so callers can treat "unknown signature" as "no bias".
 */
export function affectCompatibility(
  signature: FeatureAffectSignature,
  target: AffectVector,
): number {
  let dot = 0
  for (const [label, w] of Object.entries(signature.labels)) {
    if (typeof w !== 'number') continue
    const tw = target.weights[label as AffectLabel]
    if (typeof tw !== 'number') continue
    dot += w * tw
  }
  if (dot > 1) return 1
  if (dot < -1) return -1
  return dot
}

/**
 * Per-layer steering payload for `generateWithSteering`. Bytes are LE f32
 * of length `hidden_size * 4`. `alpha` is the scalar gain (Aurora's
 * calibration aims for total injection at ~5-15% of the residual norm).
 */
export interface LayerSteer {
  layer: number
  alpha: number
  vectorBytes: Uint8Array
}

export interface GenerationResult {
  text: string
  tokens: number[]
  durationMs: number
}

interface CassiLarqlModule {
  loadVindexOnly(path: string): Promise<VindexHandle>
  unloadVindexOnly(handle: VindexHandle): void
  getVindexConfig(handle: VindexHandle): VindexHandle['config']
  vindexTokenize(handle: VindexHandle, text: string): number[]
  vindexGateKnn(handle: VindexHandle, layer: number, tokenId: number, topK: number): FeatureHit[]
  gateEmbed(handle: VindexHandle, text: string): Float32Array
  /** Multi-token gate KNN — aggregates across all tokens via max-pool. */
  traceForward(handle: VindexHandle, promptTokens: number[], layerStart: number, layerEnd: number, topK: number): {
    features: Array<{ layer: number; featureIndex: number; score: number; label?: string; topContributingToken?: string }>
    tokensProcessed: number
    layersScanned: number
    durationMs: number
  }
  /** Multi-token gate KNN — returns per-token feature activations + density metrics. */
  traceForwardPerToken(handle: VindexHandle, promptTokens: number[], layerStart: number, layerEnd: number, topK: number): {
    tokens: Array<{ tokenIndex: number; tokenId: number; features: Array<{ layer: number; featureIndex: number; score: number; label?: string }>; featureCount: number }>
    totalUniqueFeatures: number
    tokensPerFeature: number
    featuresPerToken: number
    tokensProcessed: number
    layersScanned: number
    durationMs: number
  }
  /** Full forward pass — returns per-layer last-token residuals + optional attention. */
  vindexForward(handle: VindexHandle, promptTokens: number[], captureLayers: number[], captureAttention: boolean): {
    residuals: Array<{ layer: number; values: Buffer }>
    attention: Array<{ layer: number; heads: number[][] }>
    durationMs: number
  }
  /** A2 Slice 2: raw f32 bytes of one gate vector at (layer, feature_index). */
  gateVector(handle: VindexHandle, layer: number, featureIndex: number): Uint8Array
  /** A2 Slice 1: steered autoregressive generation via upstream's SteerHook. */
  generateWithSteering(
    handle: VindexHandle,
    promptTokens: number[],
    steers: LayerSteer[],
    maxNewTokens: number,
  ): GenerationResult
  /**
   * A2 calibration: measure typical residual L2 norms at the requested
   * layers via a single forward pass. Aurora's BaselineNormSource wraps
   * this to scale composed steering vectors to spec §4.3's recommended
   * 5–15% of residual.
   */
  measureResidualNorms(
    handle: VindexHandle,
    promptTokens: number[],
    layers: number[],
  ): { norms: Array<{ layer: number; norm: number }>; durationMs: number }
}

export interface LarqlProviderConfig {
  /** Knowledge layers to scan (default: L14-L27 for Gemma 3 4B). */
  knowledgeLayers: number[]
  /** Top-K features per layer per query. */
  featuresPerLayer: number
  /** Minimum gate score to include a relation. */
  minGateScore: number
  /** Maximum relations per entity. */
  maxRelationsPerEntity: number
  /** Maximum depth for subgraph extraction. */
  maxSubgraphDepth: number
}

export const LARQL_PROVIDER_DEFAULTS: LarqlProviderConfig = {
  knowledgeLayers: [14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27],
  featuresPerLayer: 20,
  minGateScore: 0.1,
  maxRelationsPerEntity: 30,
  maxSubgraphDepth: 2,
}

/**
 * Marker interface for providers that support Aurora cycle-id provenance.
 * Aurora's `applyCycleId` uses structural typing to detect this capability
 * without modifying the shared `ModelKnowledgeProvider` interface.
 */
export interface CycleIdAware {
  setCycleId(cycleId: string | null): void
}

/**
 * LarqlKnowledgeProvider — queries model knowledge via vindex gate KNN.
 */
export class LarqlKnowledgeProvider implements ModelKnowledgeProvider, CycleIdAware {
  private config: LarqlProviderConfig
  private logger: ILogger
  private handle: VindexHandle | null = null

  /** Multi-vindex support: source → binding. First loaded becomes default. */
  private bindings = new Map<string, VindexBinding>()
  private defaultSource: string | null = null

  /** Get all loaded vindex sources. */
  getLoadedSources(): string[] { return [...this.bindings.keys()] }
  /** Get the default (first-loaded) source name. */
  getDefaultSource(): string | null { return this.defaultSource }
  /** Get a specific binding by source name. */
  getBinding(source: string): VindexBinding | undefined { return this.bindings.get(source) }

  /** Expose vindex handle for introspection (used by InferenceTraceProvider). */
  get vindexHandle(): VindexHandle | null { return this.handle }
  private larql: CassiLarqlModule | null = null
  private loaded = false

  // Cache: entity name → describe result
  private cache = new Map<string, ModelEntity | null>()
  private maxCacheSize = 500

  // Feature fingerprints per entity (for similarity search). Capped alongside cache.
  private fingerprints = new Map<string, Map<string, number>>()

  // Optional provenance sink — every gate-KNN hit gets recorded for the
  // claustrum-vindex snapshotter. Null = recording disabled.
  private recorder: ClaustrumRecorder | null = null

  // Currently active Aurora cycle, stamped on each gate-KNN provenance row.
  // Aurora calls setCycleId() at the top of each `buildState`. Null between cycles.
  private currentCycleId: string | null = null

  // Optional overlay layer — when set, describe() with applyOverlay:true merges
  // overlay patches into base vindex results. See C3 (Bidirectional Claustrum Surgery).
  private overlay: OverlayLayer | null = null

  // Optional resolver: maps (layer, featureIndex) → Affect for affect-biased gate-KNN.
  // V4 features don't yet expose affect on this codebase; tests stub this directly.
  private featureAffectProvider: FeatureAffectProvider | null = null

  // B2: per-feature label-keyed affect signatures, populated by the
  // calibration command (B2.1b) or by tests. Distinct from the
  // legacy FeatureAffectProvider which returns continuous (v, a)
  // points; this returns sparse per-label affinities used by the
  // mode-driven RetrievalPolicy path.
  private featureAffectSignatureProvider: FeatureAffectSignatureProvider | null = null

  // B2: current affect snapshot used to resolve consonant/complementary
  // policy modes. Caller is expected to update this at the start of each
  // turn via setCurrentAffect; if unset, RetrievalPolicy mode resolution
  // falls back to a neutral target (no bias).
  private currentAffect: Affect | null = null

  constructor(
    logger: ILogger,
    config?: Partial<LarqlProviderConfig>,
  ) {
    this.logger = logger.child ? logger.child('larql-provider') : logger
    this.config = { ...LARQL_PROVIDER_DEFAULTS, ...config }
  }

  /** Attach a recorder so that future gate-KNN hits are persisted. */
  setRecorder(recorder: ClaustrumRecorder | null): void {
    this.recorder = recorder
  }

  /** Attach an overlay layer for bidirectional claustrum surgery (C3). */
  setOverlay(overlay: OverlayLayer | null): void {
    this.overlay = overlay
  }

  /**
   * Attach a feature-affect resolver used by `gateKnn` when an `affectBias`
   * is supplied. Pass `null` to disable. See FeatureAffectProvider.
   */
  setFeatureAffectProvider(provider: FeatureAffectProvider | null): void {
    this.featureAffectProvider = provider
  }

  /**
   * B2: attach a per-feature affect-signature resolver. Used by the
   * mode-driven RetrievalPolicy path (`consonant` / `complementary` /
   * `directed`). Distinct from `setFeatureAffectProvider` — the legacy
   * provider returns continuous (v, a) Affect; this one returns sparse
   * per-label signatures.
   *
   * Pass `null` to disable. When unset, RetrievalPolicy calls fall back
   * to passing hits through unchanged (compat=0 ⇒ no bias).
   */
  setFeatureAffectSignatureProvider(
    provider: FeatureAffectSignatureProvider | null,
  ): void {
    this.featureAffectSignatureProvider = provider
  }

  /**
   * B2: set the current affect snapshot used by `consonant` and
   * `complementary` policy modes to resolve target vectors. Pass `null`
   * to clear; mode resolution falls back to neutral target when unset.
   */
  setCurrentAffect(affect: Affect | null): void {
    this.currentAffect = affect
  }

  /**
   * Stamp every subsequent gate-KNN provenance row with this cycle id, so
   * the snapshotter can group features by the Aurora cycle that surfaced them.
   * Pass `null` between cycles.
   *
   * See: docs/design/claustrum-vindex.md §6 (Recording Protocol)
   */
  setCycleId(cycleId: string | null): void {
    this.currentCycleId = cycleId
  }

  /** Currently-active cycle id (mainly useful for tests + diagnostics). */
  getCycleId(): string | null {
    return this.currentCycleId
  }

  /**
   * Initialize by loading the vindex in browse-only mode.
   * Returns true if loading succeeded.
   */
  async load(vindexPath: string): Promise<boolean> {
    return this.loadVindexSource(vindexPath, 'default')
  }

  /**
   * Load an additional vindex identified by source name.
   * First loaded source becomes the default (backward compat).
   * Returns true if loading succeeded.
   */
  async loadVindexSource(vindexPath: string, source: string): Promise<boolean> {
    try {
      // @ts-ignore — cassi-larql is a native module without type declarations
      if (!this.larql) this.larql = require('cassi-larql') as CassiLarqlModule
    } catch (err) {
      this.logger.warn('cassi-larql bindings not available', { error: String(err) })
      return false
    }

    try {
      const handle = await this.larql.loadVindexOnly(vindexPath)

      // First loaded source becomes the default (backward compat).
      if (!this.handle) {
        this.handle = handle
        this.loaded = true
      }

      const config = this.larql.getVindexConfig(handle)
      this.bindings.set(source, {
        handle,
        source,
        config: {
          numLayers: config.numLayers,
          hiddenDim: config.hiddenDim,
          vocabSize: config.vocabSize,
        },
      })
      if (!this.defaultSource) this.defaultSource = source

      this.logger.info('LARQL knowledge provider loaded', {
        source,
        path: vindexPath,
        numLayers: config.numLayers,
        hiddenDim: config.hiddenDim,
        vocabSize: config.vocabSize,
        knowledgeLayers: `L${this.config.knowledgeLayers[0]}-L${this.config.knowledgeLayers[this.config.knowledgeLayers.length - 1]}`,
        totalSources: this.bindings.size,
      })

      return true
    } catch (err) {
      this.logger.error('Failed to load vindex', { source, path: vindexPath, error: String(err) })
      return false
    }
  }

  /**
   * Unload all vindexes and free resources.
   */
  unload(): void {
    if (this.larql) {
      for (const binding of this.bindings.values()) {
        this.larql.unloadVindexOnly(binding.handle)
      }
    }
    this.bindings.clear()
    this.defaultSource = null
    this.handle = null
    this.loaded = false
    this.cache.clear()
    this.logger.info('LARQL knowledge provider unloaded')
  }

  /**
   * Whether the provider is loaded and ready.
   */
  isLoaded(): boolean {
    return this.loaded
  }

  /**
   * Get the vindex config (dimensions, layer count, vocab size).
   * Used by EngramDecomposer for version stamping.
   */
  getConfig(source?: string): { numLayers: number; hiddenDim: number; vocabSize: number } | null {
    if (source) {
      const binding = this.bindings.get(source)
      return binding?.config ?? null
    }
    if (!this.handle) return null
    return {
      numLayers: this.handle.config.numLayers,
      hiddenDim: this.handle.config.hiddenDim,
      vocabSize: this.handle.config.vocabSize,
    }
  }

  /**
   * Options for describe() queries.
   *
   * applyOverlay: when true and an overlay layer is attached, merges overlay
   * patches into the base vindex results. Overlay-sourced entries carry
   * provenance metadata. Default: false.
   */
  describe(entity: string, opts?: { applyOverlay?: boolean }): ModelEntity | null {
    if (!this.loaded || !this.handle || !this.larql) return null
    const handle = this.handle
    const larql = this.larql

    // Check cache
    if (this.cache.has(entity)) {
      return this.cache.get(entity) ?? null
    }

    const tokens = larql.vindexTokenize(handle, entity)
    if (tokens.length === 0) {
      this.cacheResult(entity, null)
      return null
    }

    // Use last token (carries most semantic weight in autoregressive models)
    const queryToken = tokens[tokens.length - 1]

    const fingerprint = new Map<string, number>()
    const labeledRelations = new Map<string, { maxScore: number; layerMin: number; layerMax: number; count: number }>()

    // Collect features for the primary query token.
    const collectFeatures = (token: number, concept: string) => {
      for (const layer of this.config.knowledgeLayers) {
        const hits = larql.vindexGateKnn(
          handle, layer, token, this.config.featuresPerLayer,
        )

        if (this.recorder !== null && hits.length > 0) {
          const filtered: ClaustrumGateHit[] = []
          for (const hit of hits) {
            if (hit.score < this.config.minGateScore) continue
            filtered.push({ layer, featureIndex: hit.featureIndex, score: hit.score })
          }
          if (filtered.length > 0) {
            this.recorder.recordGateHits({
              cycleId: this.currentCycleId,
              queryConcept: concept,
              trigger: 'larql_gate_knn',
              hits: filtered,
            })
          }
        }

        for (const hit of hits) {
          if (hit.score < this.config.minGateScore) continue
          const key = `L${layer}:F${hit.featureIndex}`
          const existing = fingerprint.get(key)
          fingerprint.set(key, existing !== undefined ? Math.max(existing, hit.score) : hit.score)

          if (hit.label) {
            const existing = labeledRelations.get(hit.label)
            if (existing) {
              existing.maxScore = Math.max(existing.maxScore, hit.score)
              existing.layerMin = Math.min(existing.layerMin, layer)
              existing.layerMax = Math.max(existing.layerMax, layer)
              existing.count++
            } else {
              labeledRelations.set(hit.label, {
                maxScore: hit.score,
                layerMin: layer,
                layerMax: layer,
                count: 1,
              })
            }
          }
        }
      }
    }

    // Collect primary features using the entity's own token.
    collectFeatures(queryToken, entity)

    // Always merge lowercase features when capitalization differs — the vindex
    // tokenizer maps "Cats" → 153637 (unrelated features) whereas "cat" → 9307
    // (rich, coherent features).  Using Math.max for overlapping features preserves
    // the best from both.
    const lower = entity.toLowerCase()
    if (lower !== entity) {
      const lowerTokens = larql.vindexTokenize(handle, lower)
      if (lowerTokens.length > 0) {
        const lowerToken = lowerTokens[lowerTokens.length - 1]
        if (lowerToken !== queryToken) {
          collectFeatures(lowerToken, lower)
        }
      }
    }

    // Overlay layer merging (C3): when applyOverlay is true and an overlay exists,
    // inject overlay-sourced feature hits into the fingerprint and relations.
    const overlayAttribution = new Map<string, string>()
    if (opts?.applyOverlay && this.overlay) {
      const overlayHits = this.overlay.queryOverlay(
        this.config.knowledgeLayers,
        this.config.featuresPerLayer,
      )
      for (const hit of overlayHits) {
        const key = `L${hit.layer}:F${hit.featureIndex}`
        const pid = hit.patchId ?? 'unknown'
        if (!fingerprint.has(key)) {
          fingerprint.set(key, hit.score)
          overlayAttribution.set(key, pid)
        } else if (fingerprint.get(key)! < hit.score) {
          fingerprint.set(key, hit.score)
          overlayAttribution.set(key, pid)
        }
        if (hit.label) {
          const existing = labeledRelations.get(hit.label)
          if (!existing) {
            labeledRelations.set(hit.label, { maxScore: hit.score, layerMin: hit.layer, layerMax: hit.layer, count: 1 })
          } else {
            existing.maxScore = Math.max(existing.maxScore, hit.score)
            existing.layerMin = Math.min(existing.layerMin, hit.layer)
            existing.layerMax = Math.max(existing.layerMax, hit.layer)
            existing.count++
          }
        }
      }
    }

    if (fingerprint.size === 0) {
      this.cacheResult(entity, null)
      return null
    }

    this.fingerprints.set(entity, fingerprint)

    const modelRelations: ModelRelation[] = []
    for (const [label, data] of labeledRelations) {
      const parts = label.split(':')
      const relation = parts.length > 1 ? parts[0] : 'related_to'
      const target = parts.length > 1 ? parts.slice(1).join(':') : label

      modelRelations.push({
        relation,
        target,
        confidence: data.maxScore,
        layerMin: data.layerMin,
        layerMax: data.layerMax,
      })
    }

    // If no labeled relations, create layer-band summary relations
    if (modelRelations.length === 0) {
      const layerBands = this.summarizeByLayerBand(fingerprint)
      for (const band of layerBands) {
        modelRelations.push({
          relation: band.band,
          target: `${band.featureCount} features (peak L${band.peakLayer})`,
          confidence: band.maxScore,
          layerMin: band.layerMin,
          layerMax: band.layerMax,
        })
      }

      // Add similarity-based relations from cached fingerprints
      const similarEntities = this.findSimilarEntities(entity, fingerprint, 5)
      for (const sim of similarEntities) {
        modelRelations.push({
          relation: 'similar_to',
          target: sim.entity,
          confidence: sim.similarity * 1000,
          layerMin: this.config.knowledgeLayers[0],
          layerMax: this.config.knowledgeLayers[this.config.knowledgeLayers.length - 1],
        })
      }
    }

    // Sort by confidence descending and cap
    modelRelations.sort((a, b) => b.confidence - a.confidence)
    const capped = modelRelations.slice(0, this.config.maxRelationsPerEntity)

    const result: ModelEntity = {
      name: entity,
      relations: capped,
      totalRelations: modelRelations.length,
      ...(overlayAttribution.size > 0 ? { overlayAttribution } : {}),
    }

    this.cacheResult(entity, result)

    this.logger.debug('Entity described', {
      entity,
      relations: capped.length,
      totalFeatures: fingerprint.size,
      topRelation: capped[0]?.relation,
    })

    return result
  }

  /**
   * Get the subgraph around an entity.
   */
  subgraph(entity: string, radius: number = 1): ModelEdge[] {
    const edges: ModelEdge[] = []
    const visited = new Set<string>()
    const queue: Array<{ entity: string; depth: number }> = [{ entity, depth: 0 }]
    const maxDepth = Math.min(radius, this.config.maxSubgraphDepth)

    while (queue.length > 0) {
      const current = queue.shift()!
      if (visited.has(current.entity)) continue
      visited.add(current.entity)

      const described = this.describe(current.entity)
      if (!described) continue

      for (const rel of described.relations) {
        edges.push({
          subject: current.entity,
          relation: rel.relation,
          object: rel.target,
          confidence: rel.confidence,
          layerMin: rel.layerMin,
          layerMax: rel.layerMax,
        })

        if (current.depth < maxDepth && !visited.has(rel.target)) {
          queue.push({ entity: rel.target, depth: current.depth + 1 })
        }
      }

      // Cap total edges for performance
      if (edges.length > 200) break
    }

    return edges
  }

  /**
   * Find shortest path between two entities.
   *
   * Uses BFS through the model's knowledge graph by iteratively
   * describing entities and following relations.
   */
  shortestPath(from: string, to: string): ModelPath | null {
    if (from === to) {
      return { entities: [from], relations: [], length: 0 }
    }

    const visited = new Set<string>()
    const queue: Array<{
      entity: string
      path: string[]
      relations: string[]
    }> = [{ entity: from, path: [from], relations: [] }]

    const maxDepth = 4 // Prevent deep searches
    const targetLower = to.toLowerCase()

    while (queue.length > 0) {
      const current = queue.shift()!
      if (current.path.length > maxDepth) continue
      if (visited.has(current.entity)) continue
      visited.add(current.entity)

      const described = this.describe(current.entity)
      if (!described) continue

      for (const rel of described.relations) {
        if (rel.target.toLowerCase() === targetLower) {
          return {
            entities: [...current.path, rel.target],
            relations: [...current.relations, rel.relation],
            length: current.relations.length + 1,
          }
        }

        if (!visited.has(rel.target)) {
          queue.push({
            entity: rel.target,
            path: [...current.path, rel.target],
            relations: [...current.relations, rel.relation],
          })
        }
      }
    }

    return null
  }

  /**
   * Check if an entity exists in the model's knowledge.
   */
  exists(entity: string): boolean {
    const described = this.describe(entity)
    return described !== null && described.relations.length > 0
  }

  /**
   * Search for entities by keyword.
   *
   * Describes the query to build a fingerprint, then finds cached entities
   * with similar fingerprints. Also returns the query entity itself if
   * it has features.
   */
  search(query: string, limit: number = 5): ModelEntity[] {
    // Describe the query itself to build its fingerprint
    const self = this.describe(query)
    const results: ModelEntity[] = []

    if (self) {
      results.push(self)
    }

    // Find similar entities from cache
    const queryFp = this.fingerprints.get(query)
    if (queryFp) {
      const similar = this.findSimilarEntities(query, queryFp, limit - results.length)
      for (const sim of similar) {
        const described = this.describe(sim.entity)
        if (described) {
          results.push(described)
        }
      }
    }

    return results.slice(0, limit)
  }

  /**
   * Get raw gate KNN features for a token at a layer.
   * Useful for DreamEngine's VindexGateKnnProvider interface.
   *
   * Optional `affectBias` re-weights and re-sorts hits by blending each
   * feature's stored affect (resolved via the feature-affect provider) with
   * the base gate-KNN score. When the provider is absent or returns null
   * for a feature, alignment falls back to 0 — that hit gets no bias.
   * When `affectBias` is omitted entirely, hits pass through unchanged
   * (preserving the existing DreamEngine call-site contract).
   */
  gateKnn(
    layer: number,
    tokenId: number,
    topK: number,
    affectBias?: AffectBias,
    source?: string,
  ): FeatureHit[] {
    const h = this.resolveHandle(source)
    if (!h || !this.larql) return []
    const baseHits = this.larql.vindexGateKnn(h, layer, tokenId, topK)
    if (!affectBias) return baseHits
    return this.applyAffectBias(baseHits, layer, affectBias)
  }

  /**
   * B2 spec §5 — gate-KNN with mode-driven RetrievalPolicy.
   *
   * Variant of `gateKnn` that takes a `RetrievalPolicy` instead of the
   * legacy `AffectBias`. The mode (`consonant` / `complementary` /
   * `directed`) is resolved against `currentAffect` into an
   * `AffectVector` target; each hit's `affectCompat` is the dot product
   * of its signature with the target, clamped to [-1, +1]; the new
   * score is `baseScore * (1 - strength + strength * compat)`.
   *
   * Welfare: strength is silently capped at `RETRIEVAL_STRENGTH_CAP`
   * (0.5) unless the caller explicitly opts out via the second arg.
   * Spec constraint B2.W3.
   *
   * Falls through to the unbiased base hits when:
   *  - `policy.affectBias` is null
   *  - no signature provider is wired
   *  - mode is `consonant`/`complementary` and `currentAffect` is unset
   */
  gateKnnWithPolicy(
    layer: number,
    tokenId: number,
    topK: number,
    policy: RetrievalPolicy,
    opts?: { allowOverStrengthCap?: boolean },
  ): FeatureHit[] {
    if (!this.loaded || !this.handle || !this.larql) return []
    const baseHits = this.larql.vindexGateKnn(this.handle, layer, tokenId, topK)
    if (!policy.affectBias) return baseHits
    return this.applyRetrievalPolicy(baseHits, layer, policy.affectBias, opts ?? {})
  }

  /**
   * B2 spec §5 — re-score and re-sort hits using a mode-driven
   * `AffectBiasSpec`. Pure function over the hits + provider state;
   * does not mutate inputs.
   */
  private applyRetrievalPolicy(
    hits: FeatureHit[],
    layer: number,
    spec: AffectBiasSpec,
    opts: { allowOverStrengthCap?: boolean },
  ): FeatureHit[] {
    const provider = this.featureAffectSignatureProvider
    if (!provider) return hits

    let strength = spec.strength
    if (!opts.allowOverStrengthCap && strength > RETRIEVAL_STRENGTH_CAP) {
      this.logger.warn?.('B2 strength capped to default ceiling', {
        requested: spec.strength,
        cap: RETRIEVAL_STRENGTH_CAP,
        mode: spec.mode,
      })
      strength = RETRIEVAL_STRENGTH_CAP
    }
    if (strength < 0) strength = 0
    if (strength > 1) strength = 1

    let target: AffectVector | null
    if (spec.mode === 'directed') {
      target = spec.vector
    } else if (this.currentAffect) {
      target = resolveTargetAffectVector(spec, this.currentAffect, resolveLabel)
    } else {
      // consonant/complementary without a current-affect baseline → no-op
      return hits
    }

    const rescored = hits.map((hit) => {
      const sig = provider(layer, hit.featureIndex)
      if (!sig) return hit
      const compat = affectCompatibility(sig, target!)
      const baseScore = hit.score
      const newScore = baseScore * (1 - strength + strength * compat)
      return {
        ...hit,
        score: newScore,
        baseScore,
        affectCompat: compat,
        biasMode: spec.mode,
        biasStrength: strength,
      }
    })

    rescored.sort((a, b) => b.score - a.score)
    return rescored
  }

  /**
   * Re-score and re-sort gate-KNN hits with an affect bias.
   *
   *   newScore = (1 - weight) * baseScore + weight * affectAlignment
   *
   * affectAlignment is `affectSimilarity(bias, featureAffect)` in [0,1] when
   * the resolver returns affect for a feature, otherwise 0 (no bias).
   * Returns a new array; does not mutate inputs.
   */
  private applyAffectBias(
    hits: FeatureHit[],
    layer: number,
    affectBias: AffectBias,
  ): FeatureHit[] {
    const weight = affectBias.weight ?? DEFAULT_AFFECT_BIAS_WEIGHT
    const biasAffect: Affect = { valence: affectBias.valence, arousal: affectBias.arousal }
    const provider = this.featureAffectProvider

    const rescored = hits.map((hit) => {
      const featureAffect = provider ? provider(layer, hit.featureIndex) : null
      const alignment = featureAffect ? affectSimilarity(biasAffect, featureAffect) : 0
      const baseScore = hit.score
      const newScore = (1 - weight) * baseScore + weight * alignment
      return {
        ...hit,
        score: newScore,
        baseScore,
        affectAlignment: alignment,
      }
    })

    rescored.sort((a, b) => b.score - a.score)
    return rescored
  }

  /** Resolve a VindexHandle from source name. Falls back to default. */
  private resolveHandle(source?: string): VindexHandle | null {
    if (!source || source === this.defaultSource) return this.handle
    return this.bindings.get(source)?.handle ?? null
  }

  /**
   * Tokenize text using the vindex's bundled tokenizer.
   */
  tokenize(text: string, source?: string): number[] {
    const h = this.resolveHandle(source)
    if (!h || !this.larql) return []
    return this.larql.vindexTokenize(h, text)
  }

  /**
   * Multi-token gate KNN trace — runs gateKnn across ALL tokens in the prompt
   * and aggregates results via max-pool scoring. Returns features sorted by
   * score descending.
   *
   * Much faster than per-token gateKnn calls (one N-API round-trip instead of
   * tokens × layers calls). ~50ms for 3 tokens × 14 layers on GPU.
   */
  traceForward(
    tokens: number[],
    layerStart: number,
    layerEnd: number,
    topK: number,
    source?: string,
  ): Array<{ layer: number; featureIndex: number; score: number; label?: string; topContributingToken?: string }> {
    const h = this.resolveHandle(source)
    if (!h || !this.larql) return []
    const result = this.larql.traceForward(h, tokens, layerStart, layerEnd, topK)
    return result?.features ?? []
  }

  /**
   * Per-token gate KNN trace — returns feature activations for each token
   * individually, plus aggregate density metrics (tokensPerFeature,
   * featuresPerToken). Use for content density scoring.
   */
  traceForwardPerToken(
    tokens: number[],
    layerStart: number,
    layerEnd: number,
    topK: number,
    source?: string,
  ): {
    tokens: Array<{ tokenIndex: number; tokenId: number; features: Array<{ layer: number; featureIndex: number; score: number; label?: string }>; featureCount: number }>
    totalUniqueFeatures: number
    tokensPerFeature: number
    featuresPerToken: number
    tokensProcessed: number
    layersScanned: number
    durationMs: number
  } | null {
    const h = this.resolveHandle(source)
    if (!h || !this.larql) return null
    return this.larql.traceForwardPerToken(h, tokens, layerStart, layerEnd, topK)
  }

  /**
   * Full forward pass through the vindex model.
   *
   * Runs attention + MLP across all layers up to the max requested,
   * capturing the last token's residual at each requested layer.
   * Optionally captures per-head attention weights.
   *
   * Returns per-layer Float32Array residuals (1536-dim each) and
   * attention patterns (heads × seq_len).
   *
   * ~1s for 10 tokens × 14 layers on GPU. First call loads inference
   * weights (~2s warmup).
   */
  forward(
    tokens: number[],
    captureLayers: number[],
    captureAttention: boolean = false,
  ): {
    residuals: Array<{ layer: number; values: Float32Array }>
    attention: Array<{ layer: number; heads: number[][] }>
    durationMs: number
  } {
    if (!this.loaded || !this.handle || !this.larql) {
      return { residuals: [], attention: [], durationMs: 0 }
    }
    const raw = this.larql.vindexForward(this.handle, tokens, captureLayers, captureAttention)
    return {
      residuals: raw.residuals.map((r: any) => ({
        layer: r.layer,
        values: new Float32Array(r.values.buffer, r.values.byteOffset, r.values.byteLength / 4),
      })),
      attention: raw.attention,
      durationMs: raw.durationMs,
    }
  }

  /**
   * Generate text steered through the vindex model.
   *
   * Runs autoregressive generation with optional steering vectors
   * that boost or suppress specific features during the forward pass.
   */
  generate(
    promptTokens: number[],
    options?: {
      maxTokens?: number
      steers?: Array<{ layer: number; alpha: number; featureIndex: number }>
    },
  ): { text: string; tokens: number[]; durationMs: number } {
    if (!this.loaded || !this.handle || !this.larql) {
      return { text: '', tokens: [], durationMs: 0 }
    }
    const maxTokens = options?.maxTokens ?? 50
    // Capture narrowed non-null refs before the closure (TS doesn't keep the
    // guard's narrowing of `this.larql`/`this.handle` inside the arrow fn).
    const larql = this.larql
    const handle = this.handle
    const steerVectors = (options?.steers ?? []).map(s => {
      const gv = larql.gateVector(handle, s.layer, s.featureIndex)
      return { layer: s.layer, alpha: s.alpha, vectorBytes: Buffer.from(gv.buffer, gv.byteOffset, gv.byteLength) }
    })
    return this.larql.generateWithSteering(this.handle, promptTokens, steerVectors, maxTokens)
  }

  /**
   * A2 Slice 2: fetch one gate vector at (layer, featureIndex) as a Float32Array.
   *
   * Returns `null` when the vindex isn't loaded or the (layer, featureIndex)
   * pair is out of range. Aurora's `composeVectorProjection` calls this
   * through the `GateVectorSource` callback to fill real f32 bytes into
   * `VectorProjection.perLayer`, which then drive `generate_with_steering`.
   */
  gateVector(layer: number, featureIndex: number): Float32Array | null {
    if (!this.loaded || !this.handle || !this.larql) return null
    try {
      const bytes = this.larql.gateVector(this.handle, layer, featureIndex)
      // Use the underlying ArrayBuffer view directly without copying when
      // the offset/length permit it.
      if (bytes.byteLength % 4 !== 0) return null
      const f32 = new Float32Array(bytes.byteLength / 4)
      const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
      for (let i = 0; i < f32.length; i++) {
        f32[i] = view.getFloat32(i * 4, true)
      }
      return f32
    } catch (err) {
      this.logger.debug?.('gateVector lookup failed', { layer, featureIndex, error: String(err) })
      return null
    }
  }

  /**
   * Embed text into the vindex's hidden-state representation space.
   *
   * Tokenizes the text, runs gate KNN across the specified layers,
   * collects gate vectors (hidden-dim row for each activated feature),
   * computes a score-weighted sum, and returns the L2-normalized result
   * as a Float32Array.
   *
   * This replaces the external vLLM/Qwen3 embedding service with an
   * embedding that IS the model's own internal representation. Two
   * texts that share a concept activate the same features — their
   * gate-vector embeddings are cosine-close.
   *
   * Returns null when the vindex isn't loaded, the text is empty, or
   * no features meet the score threshold.
   */
  gateEmbed(text: string, options?: {
    /** Layers to scan. Default: L14-L27 (knowledge band for 35-layer model). */
    layers?: number[]
    /** Top-K features per layer. Default: 10. */
    featuresPerLayer?: number
    /** Minimum gate score to include a feature. Default: 0.05. */
    minScore?: number
    /** Vindex source to use. Default: first-loaded (backward compat). */
    source?: string
  }): Float32Array | null {
    const h = this.resolveHandle(options?.source)
    if (!h || !this.larql) return null
    if (!text) return null

    // Use native gate_embed when available (reads raw f16 from mmap,
    // ~10× faster than the JS path). Length >= 6 indicates the Rust
    // function accepts the patches parameter (added for causal retrieval).
    if (typeof (this.larql as any).gateEmbed === 'function') {
      try {
        const buf: Buffer = (this.larql as any).gateEmbed(
          h, text,
          options?.layers ?? null,
          options?.featuresPerLayer ?? null,
          options?.minScore ?? null,
        )
        if (!buf || buf.byteLength === 0) return null
        return new Float32Array(buf.buffer, buf.byteOffset, buf.byteLength / 4)
      } catch {
        // Fall through to JS path below
      }
    }

    // Fallback JS path (when native gate_embed is not available).
    const hiddenDim = h.config.hiddenDim
    if (!hiddenDim || hiddenDim <= 0) return null

    const layers = options?.layers ?? [14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]
    const featuresPerLayer = options?.featuresPerLayer ?? 10
    const minScore = options?.minScore ?? 0.05

    const tokens = this.larql.vindexTokenize(h, text)
    if (tokens.length === 0) return null

    const queryToken = tokens[tokens.length - 1]

    const vectors: Float32Array[] = []
    const scores: number[] = []

    for (const layer of layers) {
      const hits = this.larql.vindexGateKnn(
        h, layer, queryToken, featuresPerLayer,
      )
      for (const hit of hits) {
        if (hit.score < minScore) continue
        const vec = this.gateVector(layer, hit.featureIndex)
        if (!vec) continue
        vectors.push(vec)
        scores.push(hit.score)
      }
    }

    if (vectors.length === 0) {
      const lower = text.toLowerCase()
      if (lower !== text) return this.gateEmbed(lower, options)
      return null
    }

    const totalScore = scores.reduce((a, b) => a + b, 0)
    if (totalScore <= 0) return null

    const embedding = new Float32Array(hiddenDim)
    for (let i = 0; i < vectors.length; i++) {
      const weight = scores[i] / totalScore
      const vec = vectors[i]
      for (let j = 0; j < hiddenDim; j++) {
        embedding[j] += vec[j] * weight
      }
    }

    let norm = 0
    for (let j = 0; j < hiddenDim; j++) {
      norm += embedding[j] * embedding[j]
    }
    norm = Math.sqrt(norm)
    if (norm > 0) {
      for (let j = 0; j < hiddenDim; j++) {
        embedding[j] /= norm
      }
    }

    return embedding
  }

  /**
   * Embed text with explicit feature patching — the causal retrieval primitive.
   *
   * Each patch boosts or dampens a specific gate feature, shifting the
   * resulting embedding toward (or away from) that feature's concept direction.
   * This proves the thesis: the model's representation space IS the retrieval
   * space, and you can intervene on it causally.
   *
   * @example
   *   // Find features via gateKnn first
   *   const hits = larql.vindexGateKnn(handle, 16, queryToken, 10)
   *   // Boost a specific feature 3×
   *   const vec = provider.embedWithPatch("attention", {
   *     patches: [{ layer: 16, featureIndex: hits[0].featureIndex, boost: 3.0 }]
   *   })
   */
  embedWithPatch(
    text: string,
    options?: {
      layers?: number[]
      featuresPerLayer?: number
      minScore?: number
      patches?: Array<{ layer: number; featureIndex: number; boost: number }>
    },
  ): Float32Array | null {
    if (!this.loaded || !this.handle || !this.larql) return null
    if (!text) return null

    const patches = options?.patches ?? []

    // Use native gate_embed with patches parameter when available.
    if (typeof (this.larql as any).gateEmbed === 'function') {
      try {
        const buf: Buffer = (this.larql as any).gateEmbed(
          this.handle, text,
          options?.layers ?? null,
          options?.featuresPerLayer ?? null,
          options?.minScore ?? null,
          patches.length > 0 ? patches : null,
        )
        if (!buf || buf.byteLength === 0) return null
        return new Float32Array(buf.buffer, buf.byteOffset, buf.byteLength / 4)
      } catch {
        // Fall through to JS path below
      }
    }

    // Fallback JS path: compute base embedding, then apply patches manually.
    const base = this.gateEmbed(text, {
      layers: options?.layers,
      featuresPerLayer: options?.featuresPerLayer,
      minScore: options?.minScore,
    })
    if (!base && patches.length === 0) return null

    const hiddenDim = this.handle.config.hiddenDim
    if (!hiddenDim || hiddenDim <= 0) return null

    const embedding = base ? new Float32Array(base) : new Float32Array(hiddenDim)

    // Apply each patch: add the patched feature's gate vector × boost.
    for (const patch of patches) {
      const vec = this.gateVector(patch.layer, patch.featureIndex)
      if (!vec) continue
      for (let j = 0; j < hiddenDim; j++) {
        embedding[j] += vec[j] * patch.boost
      }
    }

    // Re-normalize after patching
    let norm = 0
    for (let j = 0; j < hiddenDim; j++) norm += embedding[j] * embedding[j]
    norm = Math.sqrt(norm)
    if (norm > 0) {
      for (let j = 0; j < hiddenDim; j++) embedding[j] /= norm
    }

    return embedding
  }

  /**
   * A2 calibration: measure typical residual L2 norm at the requested
   * layers via one forward pass over `promptText`. Returns a Map<layer,
   * norm> for the caller to cache and use as a `BaselineNormSource`.
   *
   * Returns an empty map when the vindex isn't loaded, the handle is
   * browse-only, or the underlying call fails (logged at debug level).
   *
   * Cost: one prefill + 1-token decode pass through generate_cached_hooked.
   * On Gemma 3 4B this is ~30 s on CPU, ~3 s on GPU (warm).
   */
  measureResidualNorms(
    promptText: string,
    layers: number[],
  ): Map<number, number> {
    const out = new Map<number, number>()
    if (!this.loaded || !this.handle || !this.larql) return out
    if (typeof this.larql.measureResidualNorms !== 'function') return out
    try {
      const promptTokens = this.larql.vindexTokenize(this.handle, promptText)
      if (promptTokens.length === 0) return out
      const result = this.larql.measureResidualNorms(this.handle, promptTokens, layers)
      for (const { layer, norm } of result.norms) {
        if (Number.isFinite(norm) && norm > 0) out.set(layer, norm)
      }
    } catch (err) {
      this.logger.debug?.('measureResidualNorms failed', { layers, error: String(err) })
    }
    return out
  }

  /**
   * A2 Slice 1: steered autoregressive generation.
   *
   * Runs a forward pass over `promptText` (or `promptTokens`, whichever is
   * supplied) while adding `alpha * vector` to the last-token position of
   * the post-layer residual at each requested layer. Returns the generated
   * text, token ids, and wall-clock duration.
   *
   * Returns `null` when the vindex isn't loaded, the handle is browse-only
   * (no model weights), or the underlying call fails (logged at debug level).
*
   * Cost: one prefill + up to `maxNewTokens` decode steps. On Gemma 3 4B
   * this is ~30 s/token on CPU, ~1–2 s/token on GPU.
   *
   * The `steers` array can be built directly from a `VectorProjection`:
   *
   *   const projection = aurora.getVectorProjection(undefined, state, vectorSource)
   *   if (projection) {
   *     const steers: LayerSteer[] = []
   *     for (const [layer, vec] of projection.perLayer) {
   *       if (vec.length > 0) {
   *         steers.push({
   *           layer,
   *           alpha: 0.1,
   *           vectorBytes: new Uint8Array(vec.buffer, vec.byteOffset, vec.byteLength),
   *         })
   *       }
   *     }
   *     const result = provider.generateWithSteering('The quick brown fox.', steers, 50)
   *   }
   */
  generateWithSteering(
    prompt: string | number[],
    steers: LayerSteer[],
    maxNewTokens: number,
    // When true, the BOS token (<bos>, id 2 for Gemma) is prepended
    // automatically so the model starts from a valid distribution.
    // Set false when the prompt token array already includes BOS.
    autoBos: boolean = true,
  ): GenerationResult | null {
    if (!this.loaded || !this.handle || !this.larql) return null
    if (typeof this.larql.generateWithSteering !== 'function') return null
    try {
      let promptTokens = Array.isArray(prompt)
        ? prompt
        : this.larql.vindexTokenize(this.handle, prompt)
      if (promptTokens.length === 0) return null

      // Auto-prepend BOS token for models that need it (Gemma 3/4, Llama, etc.)
      // BOS token id is model-specific; we detect it by tokenizing '<bos>'.
      if (autoBos && promptTokens[0] !== 1 && promptTokens[0] !== 2) {
        const bosTokens = this.larql.vindexTokenize(this.handle, '<bos>')
        if (bosTokens.length === 1 && bosTokens[0] > 0 && bosTokens[0] < 10) {
          promptTokens = [bosTokens[0], ...promptTokens]
        }
      }

      const result = this.larql.generateWithSteering(
        this.handle, promptTokens, steers, maxNewTokens,
      )
      return result
    } catch (err) {
      this.logger.debug?.('generateWithSteering failed', {
        maxNewTokens,
        steeringLayers: steers.map(s => s.layer),
        error: String(err),
      })
      return null
    }
  }

  /**
   * Build a `GateVectorSource` callback for `composeVectorProjection`.
   *
   * The returned function can be passed directly to Aurora's
   * `getVectorProjection(options, state, vectorSource, baselineNormSource)`:
   *
   *   const projection = aurora.getVectorProjection(
   *     { targetResidualFraction: 0.05 },
   *     aurora.currentState,
   *     provider.makeGateVectorSource(),
   *     provider.makeBaselineNormSource(residualNorms),
   *   )
   *
   * Each call to the source callback tokenizes the node's label, runs gate
   * KNN at the requested layer, and returns the top feature's gate vector
   * as a Float32Array. Returns `null` when the node has no label, the
   * layer has no matching feature, or the vindex isn't loaded.
   */
  makeGateVectorSource(): import('./projection/vector-projection.js').GateVectorSource {
    const provider = this
    return (node: import('./types.js').CognitiveNode, layer: number): Float32Array | null => {
      if (!provider.loaded || !provider.handle || !provider.larql) return null
      if (!node.label) return null
      const tokens = provider.larql.vindexTokenize(provider.handle, node.label)
      if (tokens.length === 0) return null
      const queryToken = tokens[tokens.length - 1]
      const hits = provider.larql.vindexGateKnn(provider.handle, layer, queryToken, 1)
      if (!hits || hits.length === 0) return null
      const bytes = provider.larql.gateVector(provider.handle, layer, hits[0].featureIndex)
      if (!bytes) return null
      return new Float32Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 4)
    }
  }

  /**
   * Compose a `BaselineNormSource` callback from a previously-measured
   * norm map. Pair with `composeVectorProjection`'s
   * `targetResidualFraction` to get spec §4.3 static calibration.
   *
   *   const norms = provider.measureResidualNorms('the lazy fox.', [20, 22, 24])
   *   const baselineNormSource = provider.makeBaselineNormSource(norms)
   *   aurora.getVectorProjection({ targetResidualFraction: 0.1 }, state,
   *     vectorSource, baselineNormSource)
   */
  makeBaselineNormSource(
    norms: Map<number, number>,
  ): (layer: number) => number | null {
    return (layer: number) => norms.get(layer) ?? null
  }

  /**
   * Full Aurora integration: compose residual steering vectors from the
   * current mental state and run steered generation in one call.
   *
   * Steps:
   *   1. Build a `GateVectorSource` from this provider (tokenize + gate KNN
   *      each activated node at its contributing layers)
   *   2. Run `composeVectorProjection` with the state + options
   *   3. Convert each layer's accumulated vector into `LayerSteer[]`
   *   4. Call `generateWithSteering` with the composited steers
   *
   * Returns both the generation result and the projection metadata so
   * callers can inspect what was injected (contributions, layer budget).
   *
   * Example (Aurora orchestration tick):
   *
   *   const result = provider.runSteeredGeneration(
   *     'Tell me about',
   *     aurora.currentState,
   *     50,
   *     {
   *       layerSubset: [20, 22, 24, 26],
   *       targetResidualFraction: 0.05,
   *       calibrationPrompt: 'The quick brown fox',
   *     },
   *   )
   *   if (result) {
   *     console.log(result.generation.text) // contributing:ignore
   *     // proyecto n.contributions — which nodes and how
   *   }
   */
  runSteeredGeneration(
    prompt: string,
    state: MentalState,
    maxNewTokens: number = 30,
    options?: {
      /** Only these layers receive steering vectors (default: all model layers) */
      layerSubset?: number[]
      /** Fraction of the residual norm to target (default: 0.05 = 5%) */
      targetResidualFraction?: number
      /** Prompt to use for residual-norm calibration probe (default: same as prompt) */
      calibrationPrompt?: string
      /** Layers to probe during calibration (default: all layers in layerSubset) */
      calibrationLayers?: number[]
      /** Options forwarded to `generateWithSteering` */
      autoBos?: boolean
    },
  ): { generation: GenerationResult; projection: VectorProjection } | null {
    if (!this.loaded || !this.handle || !this.larql) {
      process.stderr.write(`[LARQL] runSteeredGeneration: loaded=${this.loaded} handle=${!!this.handle} larql=${!!this.larql}\n`)
      return null
    }

    const {
      layerSubset,
      targetResidualFraction = 0.05,
      calibrationPrompt = prompt,
      calibrationLayers,
      autoBos = true,
    } = options ?? {}

    // Measure residual norms for calibration
    const normLayers = calibrationLayers ?? layerSubset ?? [20, 22, 24, 26]
    const norms = this.measureResidualNorms(calibrationPrompt, normLayers)
    const baselineNormSource = this.makeBaselineNormSource(norms)

    // Compose vector projection from the mental state
    const projection = composeVectorProjection(
      state,
      { layerSubset, targetResidualFraction },
      {},
      this.makeGateVectorSource(),
      baselineNormSource,
    )
    if (!projection) {
      process.stderr.write(`[LARQL] composeVectorProjection returned null (state nodes=${state.graph.nodes.size})\n`)
      return null
    }

    // Convert projection to LayerSteer[]
    const steers: LayerSteer[] = []
    for (const [layer, vec] of projection.perLayer) {
      if (vec.length === 0) continue
      steers.push({
        layer,
        // alpha = 1.0 because the projection already includes
        // salience * magnitudeScale via GateVectorSource + options.
        // The `targetResidualFraction` option in composeVectorProjection
        // rescales each layer's vector to `fraction * residual_norm`
        // via rescaleToCalibrationTarget, so alpha=1.0 applies it at
        // the calibrated strength.
        alpha: 1.0,
        vectorBytes: new Uint8Array(vec.buffer, vec.byteOffset, vec.byteLength),
      })
    }
    if (steers.length === 0) return null

    const generation = this.generateWithSteering(prompt, steers, maxNewTokens, autoBos)
    if (!generation) return null

    return { generation, projection }
  }

  /**
   * Create a VindexGateKnnProvider compatible with DreamEngine.
   */
  asDreamProvider(): { tokenize: (text: string) => number[]; gateKnn: (layer: number, tokenId: number, topK: number) => Array<{ featureIndex: number; score: number }> } {
    return {
      tokenize: (text: string) => this.tokenize(text),
      gateKnn: (layer: number, tokenId: number, topK: number) => this.gateKnn(layer, tokenId, topK),
    }
  }

  /**
   * Summarize a fingerprint by layer bands (syntax, knowledge, output).
   */
  private summarizeByLayerBand(fingerprint: Map<string, number>): Array<{
    band: string
    featureCount: number
    maxScore: number
    peakLayer: number
    layerMin: number
    layerMax: number
  }> {
    const bands = [
      { name: 'syntax', min: 0, max: 13 },
      { name: 'knowledge', min: 14, max: 27 },
      { name: 'output', min: 28, max: 33 },
    ]

    return bands.map(band => {
      let featureCount = 0
      let maxScore = 0
      let peakLayer = band.min
      let layerMin = 999
      let layerMax = 0

      for (const [key, score] of fingerprint) {
        const layer = parseInt(key.split(':')[0].slice(1))
        if (layer >= band.min && layer <= band.max) {
          featureCount++
          if (score > maxScore) {
            maxScore = score
            peakLayer = layer
          }
          layerMin = Math.min(layerMin, layer)
          layerMax = Math.max(layerMax, layer)
        }
      }

      return {
        band: band.name,
        featureCount,
        maxScore,
        peakLayer,
        layerMin: layerMin === 999 ? band.min : layerMin,
        layerMax: layerMax === 0 ? band.max : layerMax,
      }
    }).filter(b => b.featureCount > 0)
  }

  /**
   * Find entities with similar feature fingerprints.
   * Uses Jaccard similarity of feature sets (same approach as DreamEngine).
   */
  private findSimilarEntities(
    entity: string,
    fingerprint: Map<string, number>,
    limit: number,
  ): Array<{ entity: string; similarity: number }> {
    const results: Array<{ entity: string; similarity: number }> = []

    for (const [otherEntity, otherFp] of this.fingerprints) {
      if (otherEntity === entity) continue

      let intersection = 0
      for (const key of fingerprint.keys()) {
        if (otherFp.has(key)) intersection++
      }

      const union = fingerprint.size + otherFp.size - intersection
      if (union === 0) continue

      const similarity = intersection / union
      if (similarity > 0.05) {
        results.push({ entity: otherEntity, similarity })
      }
    }

    results.sort((a, b) => b.similarity - a.similarity)
    return results.slice(0, limit)
  }

  private cacheResult(entity: string, result: ModelEntity | null): void {
    if (this.cache.size >= this.maxCacheSize) {
      const firstKey = this.cache.keys().next().value
      if (firstKey !== undefined) {
        this.cache.delete(firstKey)
        this.fingerprints.delete(firstKey)
      }
    }
    this.cache.set(entity, result)
  }

  getCacheStats(): { size: number; maxSize: number; fingerprintCount: number } {
    return {
      size: this.cache.size,
      maxSize: this.maxCacheSize,
      fingerprintCount: this.fingerprints.size,
    }
  }
}
