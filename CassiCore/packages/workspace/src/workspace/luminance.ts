/**
 * SystemLuminanceScorer — Computes the salience of cognitive signals.
 *
 * Generalized from Constellation's KindlingEngine luminance scoring.
 * Scores each signal on four dimensions:
 *
 *   Novelty (0.25)          — Is this new relative to current workspace contents?
 *   Urgency (0.30)          — How time-sensitive is this signal?
 *   Relevance (0.25)        — How broadly useful across sessions?
 *   Source Credibility (0.20)— Has this module produced useful signals before?
 *
 * The composite score determines whether the signal crosses the ignition
 * threshold and enters the workspace (consciousness).
 */

import type {
  CognitiveSignal,
  SystemLuminanceScore,
  SystemLuminanceWeights,
  WorkspaceSlot,
  TraitVector,
} from './cognitive-signal.js'
import {
  BASE_URGENCY,
  DEFAULT_LUMINANCE_WEIGHTS,
  UNITY_PRESET,
  TRAIT_AXES,
  traitDistance,
} from './cognitive-signal.js'
import type { WorkspaceMemory } from './workspace-memory.js'


const STOP_WORDS = new Set([
  'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
  'should', 'may', 'might', 'shall', 'can', 'need', 'must', 'to', 'of',
  'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'about',
  'that', 'this', 'these', 'those', 'it', 'its', 'and', 'or', 'but',
  'not', 'no', 'if', 'then', 'else', 'when', 'while', 'which', 'who',
  'what', 'where', 'how', 'all', 'each', 'every', 'both', 'some', 'any',
  'few', 'more', 'most', 'other', 'so', 'than', 'too', 'very', 'just',
])


/**
 * Extract meaningful keywords from text for novelty/coalition matching.
 * Filters stop words and short tokens.
 */
export function extractKeywords(text: string): Set<string> {
  const words = text.toLowerCase().replace(/[^a-z0-9\s-_]/g, ' ').split(/\s+/)
  const keywords = new Set<string>()
  for (const word of words) {
    if (word.length > 3 && !STOP_WORDS.has(word)) {
      keywords.add(word)
    }
  }
  return keywords
}


/**
 * Compute keyword overlap ratio between two sets.
 * Returns 0-1 where 1 = identical keyword sets.
 */
export function keywordOverlap(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 || b.size === 0) return 0
  let shared = 0
  for (const word of a) {
    if (b.has(word)) shared++
  }
  return shared / Math.min(a.size, b.size)
}


export class SystemLuminanceScorer {
  private weights: SystemLuminanceWeights
  private workspaceTraitVector: TraitVector

  constructor(weights?: SystemLuminanceWeights) {
    this.weights = weights ?? DEFAULT_LUMINANCE_WEIGHTS
    this.workspaceTraitVector = UNITY_PRESET
  }

  /**
   * Update the workspace trait vector for trait-aware credibility scoring (C-POLY-1).
   */
  updateWorkspaceTraitVector(traitVector: TraitVector): void {
    this.workspaceTraitVector = traitVector
  }


  /**
   * Score a cognitive signal's luminance.
   *
   * @param signal - The signal to score
   * @param currentSlots - What's currently in the workspace (for novelty)
   * @param memory - Workspace memory (for source credibility)
   * @param activeSessionCount - How many sessions are active (for relevance)
   */
  score(
    signal: CognitiveSignal,
    currentSlots: WorkspaceSlot[],
    memory: WorkspaceMemory,
    activeSessionCount: number,
  ): SystemLuminanceScore {
    const novelty = this.scoreNovelty(signal, currentSlots)
    const urgency = this.scoreUrgency(signal)
    const relevance = this.scoreRelevance(signal, activeSessionCount)

    // C-POLY-1: Trait-aware credibility scoring
    let sourceCredibility = memory.getCredibility(signal.source)
    const publisherTraits = signal.metadata?.publisherTraitVector as TraitVector | undefined
    if (publisherTraits) {
      const traitMultiplier = this.computeTraitMultiplier(publisherTraits)
      sourceCredibility *= traitMultiplier
    }

    const composite = Math.max(0, Math.min(1,
      novelty * this.weights.novelty +
      urgency * this.weights.urgency +
      relevance * this.weights.relevance +
      sourceCredibility * this.weights.sourceCredibility,
    ))

    return { novelty, urgency, relevance, sourceCredibility, cognitiveResonance: 0, strategicImportance: 0, composite }
  }

  /**
   * Compute trait distance and return credibility multiplier (C-POLY-1).
   * Aligned traits get a boost (up to 1.20x), divergent traits get a penalty (down to 0.80x).
   */
  private computeTraitMultiplier(signalTraits: TraitVector): number {
    const distance = traitDistance(this.workspaceTraitVector, signalTraits)
    // Map 0-1 distance to 1.20-0.80 multiplier
    return 1.20 - distance * 0.40
  }


  /**
   * Novelty: how different is this signal from what's already in the workspace?
   * High overlap with existing slot content → low novelty.
   */
  private scoreNovelty(signal: CognitiveSignal, currentSlots: WorkspaceSlot[]): number {
    const signalKeywords = extractKeywords(signal.content)
    if (signalKeywords.size === 0) return 0.5

    let maxOverlap = 0
    for (const slot of currentSlots) {
      if (!slot.signal) continue
      const slotKeywords = extractKeywords(slot.signal.content)
      const overlap = keywordOverlap(signalKeywords, slotKeywords)
      if (overlap > maxOverlap) maxOverlap = overlap
    }

    // Content richness bonus (longer signals tend to be more informative)
    const richness = Math.min(signal.content.length / 500, 1.0) * 0.15

    // High overlap with existing content = low novelty
    return Math.max(0, Math.min(1, (1 - maxOverlap) * 0.85 + richness))
  }


  /**
   * Urgency: base urgency from signal type + optional module hint.
   */
  private scoreUrgency(signal: CognitiveSignal): number {
    const base = BASE_URGENCY[signal.type] ?? 0.5
    const hint = signal.urgencyHint ?? 0
    return Math.max(0, Math.min(1, base + hint))
  }


  /**
   * Relevance: how broadly applicable is this signal?
   * Session-specific signals score based on session count.
   * Global signals ('*') always score high.
   */
  private scoreRelevance(signal: CognitiveSignal, activeSessionCount: number): number {
    if (signal.sessionId === '*') return 0.9
    if (activeSessionCount <= 1) return 0.7
    // Session-specific signals in a multi-session context are less broadly relevant
    return 0.5
  }
}
