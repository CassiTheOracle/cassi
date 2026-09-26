/**
 * Coalition Detection — Cross-module signal amplification.
 *
 * When multiple modules independently flag related patterns, their signals
 * form a coalition and gain a luminance boost. This allows weak signals
 * from different sources to combine and cross the ignition threshold.
 *
 * A signal at 0.15 luminance that two other modules corroborate
 * can reach the 0.25 threshold — entering consciousness collectively
 * when none would have made it alone.
 *
 * Detection methods:
 *   - Keyword overlap (3+ shared terms between signals from different sources)
 *   - Session overlap (different modules signaling about the same session)
 *   - Type affinity (tension + insight on the same topic)
 *   - Temporal proximity (signals arriving in the same tick from different sources)
 */

import type { CognitiveSignal } from './cognitive-signal.js'
import { extractKeywords, keywordOverlap } from './luminance.js'


export type CoalitionBinding =
  | 'keyword_overlap'
  | 'session_overlap'
  | 'type_affinity'
  | 'temporal_proximity'

export interface Coalition {
  coalitionId: string
  memberSignalIds: string[]
  binding: CoalitionBinding
  /** Luminance boost from this coalition */
  boost: number
  formedAt: number
}


/** Boost per coalition member, capped at MAX_COALITION_BOOST total */
const BOOST_PER_MEMBER = 0.08
const MAX_COALITION_BOOST = 0.20

/** Minimum keyword overlap to form a keyword-based coalition */
const MIN_KEYWORD_OVERLAP = 0.25
const MIN_SHARED_KEYWORDS = 3

/** Type pairs that have natural affinity */
const TYPE_AFFINITIES: Array<[string, string]> = [
  ['tension', 'insight'],
  ['warning', 'observation'],
  ['tension', 'suggestion'],
  ['observation', 'convergence'],
  ['insight', 'convergence'],
]


export class CoalitionDetector {
  private coalitions = new Map<string, Coalition>()
  private signalKeywordCache = new Map<string, Set<string>>()
  private nextCoalitionId = 0


  /**
   * Check if a signal can form coalitions with pending sub-threshold signals.
   * Returns the total luminance boost from all formed coalitions.
   */
  detectCoalitions(
    signal: CognitiveSignal,
    pendingSignals: CognitiveSignal[],
  ): { boost: number; coalitions: Coalition[] } {
    const formed: Coalition[] = []
    let totalBoost = 0

    for (const pending of pendingSignals) {
      if (pending.source === signal.source) continue
      if (totalBoost >= MAX_COALITION_BOOST) break

      const binding = this.findBinding(signal, pending)
      if (!binding) continue

      const existing = this.findExistingCoalition(pending.signalId)
      if (existing) {
        // Add to existing coalition
        if (!existing.memberSignalIds.includes(signal.signalId)) {
          existing.memberSignalIds.push(signal.signalId)
          existing.boost = Math.min(MAX_COALITION_BOOST, existing.memberSignalIds.length * BOOST_PER_MEMBER)
        }
        if (!formed.includes(existing)) formed.push(existing)
      } else {
        // Form new coalition
        const coalition: Coalition = {
          coalitionId: `coalition-${this.nextCoalitionId++}`,
          memberSignalIds: [pending.signalId, signal.signalId],
          binding,
          boost: BOOST_PER_MEMBER * 2,
          formedAt: Date.now(),
        }
        this.coalitions.set(coalition.coalitionId, coalition)
        formed.push(coalition)
      }

      totalBoost = Math.min(MAX_COALITION_BOOST,
        formed.reduce((sum, c) => sum + c.boost, 0))
    }

    return { boost: totalBoost, coalitions: formed }
  }


  /**
   * Find the binding type between two signals, if any.
   */
  private findBinding(a: CognitiveSignal, b: CognitiveSignal): CoalitionBinding | null {
    // Keyword overlap (strongest binding)
    const aKeywords = this.getKeywords(a)
    const bKeywords = this.getKeywords(b)
    const overlap = keywordOverlap(aKeywords, bKeywords)
    let sharedCount = 0
    for (const k of aKeywords) { if (bKeywords.has(k)) sharedCount++ }
    if (overlap >= MIN_KEYWORD_OVERLAP && sharedCount >= MIN_SHARED_KEYWORDS) {
      return 'keyword_overlap'
    }

    // Type affinity
    for (const [typeA, typeB] of TYPE_AFFINITIES) {
      if ((a.type === typeA && b.type === typeB) || (a.type === typeB && b.type === typeA)) {
        // Must also share at least 2 keywords to prevent spurious coalitions
        if (sharedCount >= 2) return 'type_affinity'
      }
    }

    // Session overlap (different modules, same session, same tick window)
    if (a.sessionId === b.sessionId && a.sessionId !== '*') {
      if (Math.abs(a.createdAt - b.createdAt) < 5000) {
        return 'session_overlap'
      }
    }

    // Temporal proximity (different modules, same tick, any session)
    if (Math.abs(a.createdAt - b.createdAt) < 2000) {
      if (sharedCount >= 2) return 'temporal_proximity'
    }

    return null
  }


  private getKeywords(signal: CognitiveSignal): Set<string> {
    let cached = this.signalKeywordCache.get(signal.signalId)
    if (!cached) {
      cached = extractKeywords(signal.content)
      this.signalKeywordCache.set(signal.signalId, cached)
    }
    return cached
  }

  private findExistingCoalition(signalId: string): Coalition | undefined {
    for (const c of this.coalitions.values()) {
      if (c.memberSignalIds.includes(signalId)) return c
    }
    return undefined
  }


  getCoalition(id: string): Coalition | undefined {
    return this.coalitions.get(id)
  }

  getActiveCoalitions(): Coalition[] {
    return Array.from(this.coalitions.values())
  }

  /** Clean up old coalitions and keyword cache */
  prune(maxAgeMs = 300_000): void {
    const cutoff = Date.now() - maxAgeMs
    for (const [id, c] of this.coalitions) {
      if (c.formedAt < cutoff) this.coalitions.delete(id)
    }
    if (this.signalKeywordCache.size > 500) {
      this.signalKeywordCache.clear()
    }
  }
}
