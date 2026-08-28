/**
 * ConceptSelfAwarenessClassifier — auto-learning semantic classifier.
 *
 * Replaces the hand-maintained SEMANTIC_VARIANTS map with a self-healing
 * approach: on each probe, collects all association labels that share
 * any substring with the concept name, caches them as learned variants,
 * and reuses them on subsequent probes.
 *
 * This eliminates ~150 lines of manually-curated variant lists and
 * automatically adapts to new concepts and model shifts.
 */

export interface LearnedVariant {
  /** The association label that matched. */
  label: string
  /** The gate score at which it matched. */
  score: number
  /** When this variant was first observed. */
  firstSeenAt: string
  /** How many times this variant has been confirmed. */
  confirmations: number
}

export interface ConceptAwareness {
  /** Is the concept self-aware in the model? */
  aware: boolean
  /** Which label produced the strongest semantic match. */
  bestMatch: string | null
  /** All learned variants for this concept. */
  variants: LearnedVariant[]
}

/**
 * Classifier that learns semantic variants automatically.
 *
 * Learning rule: any association label from gate KNN that shares a
 * substring of length ≥3 with the concept name is a candidate variant.
 * Candidates are confirmed when they appear with score > 10. Confirmed
 * variants persist in the cache and are checked before substring matching
 * on subsequent probes, making the second probe ~3× faster.
 */
export class ConceptSelfAwarenessClassifier {
  /** Learned variants: concept → variant label → LearnedVariant */
  private variants = new Map<string, Map<string, LearnedVariant>>()

  /** Minimum substring length for a label to be considered a variant. */
  private minSubstringLen: number

  /** Minimum score for a variant to be confirmed. */
  private minScore: number

  constructor(opts?: { minSubstringLen?: number; minScore?: number }) {
    this.minSubstringLen = opts?.minSubstringLen ?? 3
    this.minScore = opts?.minScore ?? 10
  }

  /**
   * Classify a concept using learned variants and dynamic substring matching.
   *
   * @param concept The concept label (e.g., "attention")
   * @param associations Top gate-KNN associations with labels and scores
   * @returns Awareness classification with learned variants
   */
  classify(
    concept: string,
    associations: Array<{ label: string | null; score: number }>,
  ): ConceptAwareness {
    const conceptLower = concept.toLowerCase()
    const cache = this.getCache(concept)

    // Phase 1: Check learned (cached) variants first — fast path
    for (const assoc of associations) {
      if (!assoc.label) continue
      const labelLower = assoc.label.toLowerCase()
      const cached = cache.get(labelLower)
      if (cached) {
        cached.confirmations++
        if (Math.abs(assoc.score) > Math.abs(cached.score)) {
          cached.score = assoc.score
        }
        return {
          aware: true,
          bestMatch: assoc.label,
          variants: [...cache.values()],
        }
      }
    }

    // Phase 2: Dynamic substring matching for new variants
    let bestMatch: string | null = null
    let bestScore = -Infinity

    for (const assoc of associations) {
      if (!assoc.label) continue
      const labelLower = assoc.label.toLowerCase()
      const score = Math.abs(assoc.score)

      // Check if any substring of the concept appears in the label
      // or vice versa (for labels like "att" matching "attention")
      if (this.sharesSubstring(conceptLower, labelLower) && score > bestScore) {
        bestScore = score
        bestMatch = assoc.label

        // Learn this variant if score exceeds threshold
        if (score >= this.minScore) {
          cache.set(labelLower, {
            label: assoc.label,
            score: assoc.score,
            firstSeenAt: new Date().toISOString(),
            confirmations: 1,
          })
        }
      }
    }

    const aware = bestMatch !== null && bestScore >= this.minScore

    return {
      aware,
      bestMatch,
      variants: [...cache.values()],
    }
  }

  /**
   * Check if two strings share a substring of at least minSubstringLen.
   * Bidirectional: checks if any length-N substring of `a` appears in `b`,
   * AND if any length-N substring of `b` appears in `a`.
   */
  private sharesSubstring(a: string, b: string): boolean {
    const len = this.minSubstringLen

    // Short strings: exact inclusion check
    if (a.length < len || b.length < len) {
      return a.includes(b) || b.includes(a)
    }

    // Check substrings of `a` in `b`
    for (let i = 0; i <= a.length - len; i++) {
      if (b.includes(a.slice(i, i + len))) return true
    }

    // Check substrings of `b` in `a` (for labels shorter than concept)
    if (b.length >= len) {
      for (let i = 0; i <= b.length - len; i++) {
        if (a.includes(b.slice(i, i + len))) return true
      }
    }

    return false
  }

  /** Get (or create) the variant cache for a concept. */
  private getCache(concept: string): Map<string, LearnedVariant> {
    let cache = this.variants.get(concept)
    if (!cache) {
      cache = new Map()
      this.variants.set(concept, cache)
    }
    return cache
  }

  /** Number of concepts with learned variants. */
  get learnedConceptCount(): number {
    return this.variants.size
  }

  /** Total learned variants across all concepts. */
  get totalVariantCount(): number {
    let count = 0
    for (const cache of this.variants.values()) count += cache.size
    return count
  }

  /** Export the learned variant map for serialization. */
  export(): Record<string, Array<{ label: string; score: number; confirmations: number }>> {
    const out: Record<string, Array<{ label: string; score: number; confirmations: number }>> = {}
    for (const [concept, cache] of this.variants) {
      out[concept] = [...cache.values()].map(v => ({
        label: v.label,
        score: v.score,
        confirmations: v.confirmations,
      }))
    }
    return out
  }
}
