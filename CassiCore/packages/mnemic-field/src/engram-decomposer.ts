/**
 * EngramDecomposer — Write-time structural decomposition of engram content.
 *
 * Decomposes long engram content into sentence-level feature fingerprints
 * at store time, enabling zero-cost read-time selection via feature overlap.
 *
 * Design: decompose once at write, select at read. No query-time distillation.
 *
 * The decomposition produces:
 * - Sentences (split by the existing splitSentences from llm-reranker)
 * - Per-sentence gate-vector feature fingerprints via traceForwardPerToken
 * - Content density metrics (Yin's heuristic + V-Field tokens-per-feature)
 * - Version stamp for model swap detection
 *
 * At read time, the query's gate vector is compared against sentence features
 * via set intersection — O(n*m) where n=features per sentence (~10-30) and
 * m=query features (~30-50). No forward pass needed at read time.
 */

import type { ILogger } from '@cassicore/foundation'
import type { LarqlKnowledgeProvider } from './vendor/core/intelligence/aurora/larql-provider.js'
import { splitSentences } from './llm-reranker.js'
import { createHash } from 'node:crypto'

/** Sentence-level feature fingerprint. */
export interface SentenceFeature {
  /** Sentence text, truncated to 200 chars for storage. */
  text: string
  /** Gate feature keys activated by this sentence: ["L14:F42", "L18:F7", ...] */
  features: string[]
  /** Token count for this sentence (for token budget math). */
  tokenCount: number
}

/** Density metrics for an engram's content. */
export interface DensityMetrics {
  /** Heuristic content density [0,1]. Higher = denser. */
  contentDensity: number
  /** tokens_processed / unique_features — higher = more verbose. */
  tokensPerFeature: number
  /** unique_features / tokens_processed — higher = denser. */
  featuresPerToken: number
  /** Total sentences decomposed. */
  sentenceCount: number
}

/** Full decomposition result — stored in engram metadata. */
export interface DecomposedContent {
  /** Model identifier + extraction config hash. Gates feature validity. */
  vindexVersion: string
  /** Per-sentence feature fingerprints. */
  entries: SentenceFeature[]
  /** Aggregate density metrics. */
  density: DensityMetrics
}

/** Configuration for the decomposer. */
export interface DecomposerConfig {
  /** Knowledge layers for feature extraction (default: [14..27]). */
  knowledgeLayers?: number[]
  /** Top-K features per layer per token (default: 10). */
  featuresPerLayer?: number
  /** Maximum sentence length in chars (default: 200). */
  maxSentenceChars?: number
  /** Minimum content length to decompose (default: 300). */
  minContentLength?: number
  /** Skip sentence features above this density (default: 0.6). */
  denseSkipThreshold?: number
  /** Decompose aggressively below this density (default: 0.3). */
  aggressiveThreshold?: number
}

const DECOMPOSER_DEFAULTS: Required<DecomposerConfig> = {
  knowledgeLayers: [14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27],
  featuresPerLayer: 10,
  maxSentenceChars: 200,
  minContentLength: 300,
  denseSkipThreshold: 0.6,
  aggressiveThreshold: 0.3,
}

// English stop words — same set used in Thalamus scorer for consistency.
const STOP_WORDS = new Set([
  'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'shall',
  'should', 'may', 'might', 'can', 'could', 'that', 'which', 'who',
  'whom', 'this', 'these', 'those', 'i', 'me', 'my', 'we', 'our',
  'you', 'your', 'he', 'him', 'his', 'she', 'her', 'it', 'its',
  'they', 'them', 'their', 'what', 'where', 'when', 'how', 'not', 'no',
  'nor', 'as', 'if', 'or', 'and', 'but', 'to', 'of', 'in', 'for',
  'on', 'with', 'at', 'by', 'from', 'into', 'about', 'up', 'out',
])

/**
 * Compute content density via heuristic — zero-cost, no model calls.
 *
 * High density = information-rich content (code, structured data).
 * Low density = verbose prose, filler-heavy text.
 *
 * Components:
 * - Type-token ratio (vocabulary richness)
 * - Stop-word ratio (content word ratio)
 * - Structural density (code markers, headers)
 * - Line length sanity
 */
export function contentDensity(content: string): number {
  if (!content || content.length < 30) return 0

  const words = content.toLowerCase().match(/[a-z_][a-z0-9_]{2,}/g) ?? []
  const uniqueWords = new Set(words).size
  const ttr = words.length > 0 ? uniqueWords / words.length : 0

  const stopCount = words.filter(w => STOP_WORDS.has(w)).length
  const stopRatio = words.length > 0 ? stopCount / words.length : 0

  const lines = content.split('\n')
  const codeLines = lines.filter(l =>
    /^\s*(function |class |export |const |let |var |if |for |while |\/\/|#|import |return |type |interface |enum |struct |impl |pub |fn |def |async |await )/.test(l)
  ).length
  const structuralRatio = lines.length > 0 ? codeLines / lines.length : 0

  const avgLineLen = lines.length > 0 ? content.length / lines.length : 0
  const lineLenScore = avgLineLen > 20 && avgLineLen < 120 ? 1.0 : 0.5

  // Composite: weighted combination
  const density = (
    0.35 * ttr +
    0.25 * (1 - stopRatio) +
    0.25 * structuralRatio +
    0.15 * lineLenScore
  )

  return Math.max(0, Math.min(1, density))
}

/**
 * Convert a feature activation result to a set of feature keys.
 * Keys are "L{layer}:F{featureIndex}" strings — stable identifiers
 * that survive serialization and enable O(1) set intersection.
 */
export function featuresToKeySet(
  features: Array<{ layer: number; featureIndex: number }>,
  source?: string,
): Set<string> {
  const keys = new Set<string>()
  for (const f of features) {
    const key = `L${f.layer}:F${f.featureIndex}`
    keys.add(source ? `${source}:${key}` : key)
  }
  return keys
}

/**
 * Score sentences against a query feature set via overlap.
 * Returns sentences sorted by feature overlap descending.
 * Pure set intersection — no model calls, O(n*m) where n=features per
 * sentence and m=query features.
 */
export function scoreSentencesByOverlap(
  sentences: SentenceFeature[],
  queryFeatures: Set<string>,
): Array<{ text: string; overlap: number; tokenCount: number }> {
  return sentences
    .map(s => ({
      text: s.text,
      overlap: s.features.filter(f => queryFeatures.has(f)).length,
      tokenCount: s.tokenCount,
    }))
    .sort((a, b) => b.overlap - a.overlap)
}

export class EngramDecomposer {
  private logger: ILogger
  private provider: LarqlKnowledgeProvider
  private config: Required<DecomposerConfig>
  private _vindexVersion: string | null = null

  constructor(
    logger: ILogger,
    provider: LarqlKnowledgeProvider,
    config?: Partial<DecomposerConfig>,
  ) {
    this.logger = logger.child?.('engram-decomposer') ?? logger
    this.provider = provider
    this.config = { ...DECOMPOSER_DEFAULTS, ...config }
  }

  /** Whether the provider is loaded and ready. */
  isReady(): boolean {
    return this.provider.isLoaded()
  }

  /**
   * Get the active vindex version string.
   * Combines model dimensions into a stable identifier.
   * Cached after first call — model doesn't change within a session.
   */
  getVindexVersion(): string {
    if (this._vindexVersion) return this._vindexVersion
    try {
      const config = this.provider.getConfig()
      const raw = `${config.numLayers}-${config.hiddenDim}-${config.vocabSize}`
      this._vindexVersion = createHash('sha256').update(raw).digest('hex').slice(0, 12)
      return this._vindexVersion
    } catch {
      this._vindexVersion = 'unknown'
      return 'unknown'
    }
  }

  /**
   * Decompose engram content into structural layers.
   *
   * Pipeline:
   * 1. contentDensity() — heuristic density score
   * 2. Gate decomposition depth based on density
   * 3. splitSentences() — break into sentences
   * 4. traceForwardPerToken() — per-sentence feature fingerprints
   * 5. Build DecomposedContent result
   *
   * Returns null if content is too short to decompose.
   */
  decompose(content: string): DecomposedContent | null {
    if (!content || content.length < this.config.minContentLength) return null
    if (!this.isReady()) return null

    // Step 1: Heuristic density
    const density = contentDensity(content)

    // Step 2: Dense content — skip sentence features, just record density
    if (density > this.config.denseSkipThreshold) {
      return {
        vindexVersion: this.getVindexVersion(),
        entries: [],
        density: {
          contentDensity: density,
          tokensPerFeature: 0,
          featuresPerToken: 0,
          sentenceCount: 0,
        },
      }
    }

    // Step 3: Split into sentences
    const sentences = splitSentences(content, this.config.maxSentenceChars)
    if (sentences.length === 0) return null

    // For aggressive decomposition (low density), limit to shorter sentences
    const maxLen = density < this.config.aggressiveThreshold
      ? Math.floor(this.config.maxSentenceChars * 0.7)
      : this.config.maxSentenceChars
    const trimmed = sentences.map(s => s.length > maxLen ? s.slice(0, maxLen) : s)

    // Step 4: Batch tokenize and trace all sentences
    try {
      const layerStart = this.config.knowledgeLayers[0]
      const layerEnd = this.config.knowledgeLayers[this.config.knowledgeLayers.length - 1]

      const entries: SentenceFeature[] = []
      let totalTokens = 0
      let totalUniqueFeatures = 0

      for (const sentence of trimmed) {
        // Tokenize the sentence
        const tokens = this.provider.tokenize(sentence)
        if (tokens.length === 0) {
          entries.push({ text: sentence.slice(0, this.config.maxSentenceChars), features: [], tokenCount: 0 })
          continue
        }

        // Run per-token trace
        const result = this.provider.traceForwardPerToken(
          tokens,
          layerStart,
          layerEnd,
          this.config.featuresPerLayer,
        )

        if (!result) {
          entries.push({ text: sentence.slice(0, this.config.maxSentenceChars), features: [], tokenCount: tokens.length })
          continue
        }

        // Extract unique feature keys from all tokens
        const featureKeys = new Set<string>()
        for (const tok of result.tokens) {
          for (const f of tok.features) {
            featureKeys.add(`L${f.layer}:F${f.featureIndex}`)
          }
        }

        entries.push({
          text: sentence.slice(0, this.config.maxSentenceChars),
          features: [...featureKeys],
          tokenCount: tokens.length,
        })
        totalTokens += tokens.length
        totalUniqueFeatures += featureKeys.size
      }

      const avgFeaturesPerSentence = entries.length > 0
        ? totalUniqueFeatures / entries.length
        : 0

      return {
        vindexVersion: this.getVindexVersion(),
        entries,
        density: {
          contentDensity: density,
          tokensPerFeature: totalUniqueFeatures > 0 ? totalTokens / totalUniqueFeatures : 0,
          featuresPerToken: totalTokens > 0 ? totalUniqueFeatures / totalTokens : 0,
          sentenceCount: sentences.length,
        },
      }
    } catch (err) {
      this.logger.debug('Decomposition failed, returning density-only result', { error: String(err) })
      return {
        vindexVersion: this.getVindexVersion(),
        entries: [],
        density: {
          contentDensity: density,
          tokensPerFeature: 0,
          featuresPerToken: 0,
          sentenceCount: sentences.length,
        },
      }
    }
  }

  /**
   * Extract feature keys from a query string.
   * Used at read time for feature-overlap selection.
   *
   * This is the read-time counterpart to the write-time sentence fingerprinting.
   * Same V-Field infrastructure, just applied to the query instead of content.
   */
  getQueryFeatures(query: string): Set<string> {
    const empty = new Set<string>()
    if (!this.isReady() || !query) return empty

    try {
      const tokens = this.provider.tokenize(query)
      if (tokens.length === 0) return empty

      const layerStart = this.config.knowledgeLayers[0]
      const layerEnd = this.config.knowledgeLayers[this.config.knowledgeLayers.length - 1]

      const result = this.provider.traceForwardPerToken(
        tokens,
        layerStart,
        layerEnd,
        this.config.featuresPerLayer,
      )

      if (!result) return empty

      const keys = new Set<string>()
      for (const tok of result.tokens) {
        for (const f of tok.features) {
          keys.add(`L${f.layer}:F${f.featureIndex}`)
        }
      }
      return keys
    } catch (err) {
      this.logger.debug('Query feature extraction failed', { error: String(err) })
      return empty
    }
  }
}
