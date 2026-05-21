/**
 * Engram Decomposition Utilities
 *
 * Write-time decomposition of engram content into structural layers.
 * At ingestion, content is split into sentences and each sentence gets
 * a feature fingerprint via the V-Field gate KNN. At retrieval time,
 * sentences are selected by feature overlap with the query — zero LLM
 * calls, zero re-embedding, just set intersection.
 *
 * Design: decompose once at write, select at read. See:
 *   .hermes/plans/2026-05-20_engram-content-distiller.md
 */

import type { ILogger } from '../../../types/interfaces.js'

/** A sentence with its pre-computed feature fingerprint. */
export interface SentenceFeature {
  /** The sentence text (truncated to 200 chars for storage). */
  text: string
  /** Feature keys activated by this sentence: ["L14:F42", "L18:F7", ...]. */
  features: string[]
  /** Token count for budget math. */
  tokenCount: number
}

/** Density signals — intrinsic properties of the text, model-agnostic. */
export interface DensityMetrics {
  /** Heuristic content density [0,1] — higher = denser. */
  contentDensity: number
  /** tokens_processed / unique_features — higher = more verbose. */
  tokensPerFeature: number
  /** unique_features / tokens_processed — higher = denser. */
  featuresPerToken: number
  /** Total sentences decomposed. */
  sentenceCount: number
}

/** The full metadata shape stored on engram.metadata.sentences. */
export interface DecompositionMetadata {
  /** Model identifier + extraction config hash. Gates feature validity. */
  vindexVersion: string
  /** Sentence entries with feature fingerprints. */
  entries: SentenceFeature[]
  /** Aggregate density signals. */
  density: DensityMetrics
}

/** Minimal provider interface for decomposition. Matches LarqlKnowledgeProvider. */
export interface DecomposerProvider {
  tokenize(text: string): number[]
  traceForwardPerToken(
    tokens: number[],
    layerStart: number,
    layerEnd: number,
    topK: number,
  ): {
    tokens: Array<{
      tokenIndex: number
      tokenId: number
      features: Array<{ layer: number; featureIndex: number; score: number; label?: string }>
      featureCount: number
    }>
    totalUniqueFeatures: number
    tokensPerFeature: number
    featuresPerToken: number
    tokensProcessed: number
    layersScanned: number
    durationMs: number
  } | null
}

/** Knowledge layers to scan for feature extraction. */
export const KNOWLEDGE_LAYER_START = 14
export const KNOWLEDGE_LAYER_END = 28

/** Top-K features per token per layer. */
export const FEATURE_TOP_K = 10

/** Max characters per sentence text stored in metadata. */
export const MAX_SENTENCE_CHARS = 200

/** Density thresholds for decomposition depth. */
export const DENSITY_THRESHOLDS = {
  /** Above this: skip sentence features (content is already dense). */
  dense: 0.6,
  /** Below this: aggressive decomposition. */
  verbose: 0.3,
} as const

const STOP_WORDS = new Set([
  'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'shall',
  'should', 'may', 'might', 'can', 'could', 'that', 'which', 'who',
  'whom', 'this', 'these', 'those', 'i', 'me', 'my', 'we', 'our',
  'you', 'your', 'he', 'him', 'his', 'she', 'her', 'it', 'its',
  'they', 'them', 'their', 'what', 'where', 'when', 'how', 'not',
  'no', 'nor', 'as', 'if', 'or', 'and', 'but', 'to', 'of', 'in',
  'for', 'on', 'with', 'at', 'by', 'from', 'into',
])

/**
 * Compute content density using lexical and structural signals.
 * Zero-cost, no model calls. Returns [0,1] — higher = denser.
 *
 * High density: code, structured data, terse prose.
 * Low density: verbose prose, filler-heavy conversation.
 */
export function contentDensity(content: string): number {
  if (!content || content.length < 30) return 0

  // Type-token ratio (unique words / total words) — vocabulary richness
  const words = content.toLowerCase().match(/[a-z_][a-z0-9_]{2,}/g) ?? []
  const uniqueWords = new Set(words).size
  const ttr = words.length > 0 ? uniqueWords / words.length : 0

  // Stop-word ratio — lower = more content-dense
  const stopCount = words.filter(w => STOP_WORDS.has(w)).length
  const stopRatio = words.length > 0 ? stopCount / words.length : 0

  // Structural density — code markers, headers, list items
  const lines = content.split('\n')
  const codeLines = lines.filter(l =>
    /^\s*(function |class |export |const |let |var |if |for |while |\/\/|#|import |return )/.test(l),
  ).length
  const structuralRatio = lines.length > 0 ? codeLines / lines.length : 0

  // Average line length — very short lines = list/enum, very long = prose blob
  const avgLineLen = lines.length > 0 ? content.length / lines.length : 0
  const lineLenScore = avgLineLen > 20 && avgLineLen < 120 ? 1.0 : 0.5

  // Composite: weighted combination
  return Math.max(0, Math.min(1,
    0.35 * ttr +
    0.25 * (1 - stopRatio) +
    0.25 * structuralRatio +
    0.15 * lineLenScore,
  ))
}

/** Format a feature key: "L{layer}:F{featureIndex}". */
export function featureKey(layer: number, featureIndex: number): string {
  return `L${layer}:F${featureIndex}`
}

/**
 * Extract feature keys from a query text via the V-Field.
 * One N-API call — tokenize + traceForwardPerToken.
 * Returns a Set of feature keys for O(1) intersection.
 *
 * This is the read-time counterpart to write-time sentence fingerprinting.
 */
export function gateKnnFeatureSet(
  text: string,
  provider: DecomposerProvider,
  layerStart: number = KNOWLEDGE_LAYER_START,
  layerEnd: number = KNOWLEDGE_LAYER_END,
  topK: number = FEATURE_TOP_K,
): Set<string> {
  const tokens = provider.tokenize(text)
  if (tokens.length === 0) return new Set()

  const result = provider.traceForwardPerToken(tokens, layerStart, layerEnd, topK)
  if (!result) return new Set()

  const features = new Set<string>()
  for (const tok of result.tokens) {
    for (const f of tok.features) {
      features.add(featureKey(f.layer, f.featureIndex))
    }
  }
  return features
}

/**
 * Score a sentence's features against a query feature set.
 * Returns the count of overlapping feature keys.
 */
export function featureOverlap(
  sentenceFeatures: string[],
  queryFeatures: Set<string>,
): number {
  let count = 0
  for (const f of sentenceFeatures) {
    if (queryFeatures.has(f)) count++
  }
  return count
}

/**
 * Select the best sentences from an engram for a given query.
 * Uses pre-computed feature fingerprints — zero model calls at read time.
 *
 * @param decomposition - The engram's metadata.sentences
 * @param queryFeatures - Feature keys extracted from the query
 * @param tokenBudget - Max tokens to fill
 * @returns Selected sentence texts joined with newlines
 */
export function selectSentences(
  decomposition: DecompositionMetadata,
  queryFeatures: Set<string>,
  tokenBudget: number,
): string {
  if (!decomposition.entries || decomposition.entries.length === 0) return ''

  // Score each sentence by feature overlap
  const scored = decomposition.entries.map(entry => ({
    text: entry.text,
    score: featureOverlap(entry.features, queryFeatures),
    tokenCount: entry.tokenCount,
  }))

  // Sort by overlap descending, then by position (preserve order for ties)
  scored.sort((a, b) => b.score - a.score)

  // Greedy select until token budget
  const selected: Array<{ text: string; tokenCount: number }> = []
  let usedTokens = 0
  for (const s of scored) {
    if (usedTokens + s.tokenCount > tokenBudget) continue
    selected.push(s)
    usedTokens += s.tokenCount
  }

  // Re-sort by original position (order within the engram)
  const originalOrder = new Map<string, number>()
  for (let i = 0; i < decomposition.entries.length; i++) {
    originalOrder.set(decomposition.entries[i].text, i)
  }
  selected.sort((a, b) => (originalOrder.get(a.text) ?? 0) - (originalOrder.get(b.text) ?? 0))

  return selected.map(s => s.text).join('\n')
}

/**
 * Get the active vindex version string.
 * Combines extraction config for cache invalidation.
 * When the model changes, this string changes, invalidating
 * all stored feature fingerprints.
 */
export function getVindexVersion(): string {
  const layerRange = `${KNOWLEDGE_LAYER_START}-${KNOWLEDGE_LAYER_END}`
  return `vindex:L${layerRange}:K${FEATURE_TOP_K}`
}

/**
 * Check if a decomposition's feature fingerprints are still valid.
 */
export function isDecompositionFresh(decomposition: DecompositionMetadata): boolean {
  return decomposition.vindexVersion === getVindexVersion()
}
