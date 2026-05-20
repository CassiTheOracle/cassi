/**
 * EngramQualityScorer — scores engram content quality via attention focus.
 *
 * Uses the model's own attention patterns as a quality signal. Coherent,
 * information-rich content produces focused attention (high Gini coefficient)
 * while structural/junk content produces diffuse attention (low Gini).
 *
 * The forward pass is expensive (~1s per engram on GPU), so scoring is
 * designed to run asynchronously (fire-and-forget from store, or batched).
 */

import type { ILogger } from '../../../types/interfaces.js'

export interface QualityScore {
  /** 0-1 score; higher = better quality. */
  score: number
  /** Average attention Gini coefficient across knowledge-layer heads. */
  attentionGini: number
  /** Layer used for scoring. */
  layer: number
  /** Number of attention heads averaged. */
  heads: number
  /** Forward pass duration in ms. */
  durationMs: number
}

/** Provider interface — the subset of LarqlKnowledgeProvider we need. */
export interface ForwardProvider {
  tokenize(text: string): number[]
  forward(
    tokens: number[],
    captureLayers: number[],
    captureAttention: boolean,
  ): {
    residuals: Array<{ layer: number; values: Float32Array }>
    attention: Array<{ layer: number; heads: number[][] }>
    durationMs: number
  }
}

export class EngramQualityScorer {
  private logger: ILogger
  private provider: ForwardProvider | null = null
  private ready = false

  /** Layer at which to capture attention for scoring (knowledge layer). */
  private readonly SCORE_LAYER = 20

  constructor(logger: ILogger) {
    this.logger = logger.child?.('engram-quality') ?? logger
  }

  /** Wire the forward-capable provider. */
  setProvider(provider: ForwardProvider | null): void {
    this.provider = provider
    this.ready = !!provider
    this.logger.info('EngramQualityScorer provider set', { ready: this.ready })
  }

  isReady(): boolean {
    return this.ready
  }

  /**
   * Score an engram's content quality using attention Gini.
   *
   * Computes the Gini coefficient of the attention distribution at a
   * knowledge layer (L20). High Gini = focused attention on key tokens
   * = coherent, information-rich content.
   *
   * Returns null if the provider isn't ready or the content is too short.
   */
  scoreContent(content: string): QualityScore | null {
    if (!this.ready || !this.provider) return null
    if (!content || content.length < 30) return null

    const start = performance.now()

    try {
      const tokens = this.provider.tokenize(content.substring(0, 4000))
      if (tokens.length < 5) return null

      const fwd = this.provider.forward(tokens, [this.SCORE_LAYER], true)

      if (!fwd.attention || fwd.attention.length === 0) return null

      const layerAttn = fwd.attention[0]
      const headGinis = layerAttn.heads.map(h => giniCoefficient(h))
      const avgGini = headGinis.reduce((s, g) => s + g, 0) / headGinis.length

      // Gini typically ranges 0.5 (unfocused) to 0.85 (very focused).
      // Map to 0-1 quality: gini 0.5→0, gini 0.85→1
      const score = Math.max(0, Math.min(1, (avgGini - 0.5) / 0.35))

      return {
        score,
        attentionGini: avgGini,
        layer: this.SCORE_LAYER,
        heads: headGinis.length,
        durationMs: performance.now() - start,
      }
    } catch (err) {
      this.logger.debug?.('EngramQualityScorer.scoreContent failed', {
        error: String(err),
      })
      return null
    }
  }
}

/**
 * Gini coefficient of an array.
 * 0 = all elements equal, 1 = one element has everything.
 */
function giniCoefficient(arr: number[]): number {
  const n = arr.length
  if (n === 0) return 0

  // Sort ascending
  const sorted = [...arr].sort((a, b) => a - b)

  // Gini = (2 * sum(i * x_i)) / (n * sum(x_i)) - (n + 1) / n
  let weightedSum = 0
  let totalSum = 0
  for (let i = 0; i < n; i++) {
    weightedSum += sorted[i] * (i + 1)
    totalSum += sorted[i]
  }

  if (totalSum === 0) return 0
  return (2 * weightedSum) / (n * totalSum) - (n + 1) / n
}
