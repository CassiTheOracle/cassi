/**
 * Meditation Feedback — Automatic training signals for neural kindling.
 *
 * During meditation, the Mnemic Field retrieves memories (kindling, injection,
 * or context surfacing). After the session, we determine which retrieved
 * memories were actually useful based on whether they informed the meditation's
 * outputs (insights, bridges, abstractions, or synthesis).
 *
 * This creates a closed learning loop:
 *   Meditation retrieves → Feedback computed → Mnemic Field learns → Better retrieval next time
 *
 * Phase 1: Organizing mode only (highest confidence signal).
 * Phase 2: Extend to focused, self-modeling, passive, active, and reflective modes.
 */

import type { ILogger } from '../../../../types/interfaces.js'
import type { MnemicField } from '../../mnemic-field/index.js'

/**
 * Tracks which engrams were retrieved and which were actually used during
 * a meditation session. After the session, computes feedback signals
 * for the Mnemic Field's neural kindling system.
 */
export class MeditationFeedbackTracker {
  /** Engrams that were retrieved/kindled during this session */
  private retrieved = new Map<string, { context: string; timestamp: number }>()
  
  /** Engrams that were actively used (referenced in operations or outputs) */
  private used = new Set<string>()
  
  /** Engrams whose retrieval led to successful operations */
  private productive = new Set<string>()
  
  /** Engrams that were retrieved but led to no action */
  private unproductive = new Set<string>()

  constructor(
    private logger: ILogger,
    private sessionId: string,
  ) {}

  /**
   * Record that specific engrams were retrieved/kindled.
   * Called when kindling operations surface engrams.
   */
  recordRetrieved(engramIds: string[], context: string): void {
    const now = Date.now()
    for (const id of engramIds) {
      if (!this.retrieved.has(id)) {
        this.retrieved.set(id, { context, timestamp: now })
      }
    }
  }

  /**
   * Record that specific engrams were actively used in an operation.
   * Called when engrams are referenced in bridges, assignments, or synthesis.
   */
  recordUsed(engramIds: string[]): void {
    for (const id of engramIds) {
      if (this.retrieved.has(id)) {
        this.used.add(id)
      }
    }
  }

  /**
   * Record that retrieval of these engrams led to a productive outcome.
   * Called when kindling leads to successful bridges, abstractions, etc.
   */
  recordProductive(engramIds: string[]): void {
    for (const id of engramIds) {
      if (this.retrieved.has(id)) {
        this.productive.add(id)
        this.used.add(id)
      }
    }
  }

  /**
   * Record that retrieval of these engrams led to no action.
   * Called when kindled regions were explored but nothing was done with them.
   */
  recordUnproductive(engramIds: string[]): void {
    for (const id of engramIds) {
      if (this.retrieved.has(id) && !this.used.has(id)) {
        this.unproductive.add(id)
      }
    }
  }

  /**
   * Compute feedback signals from this session's tracking data.
   * 
   * Returns a map of engram ID → helpfulness boolean.
   * - true: engram was retrieved AND used/productive
   * - false: engram was retrieved but NOT used (unproductive)
   */
  computeFeedback(): Record<string, boolean> {
    const feedback: Record<string, boolean> = {}

    for (const [engramId] of this.retrieved) {
      if (this.productive.has(engramId) || this.used.has(engramId)) {
        feedback[engramId] = true
      } else {
        feedback[engramId] = false
      }
    }

    return feedback
  }

  /**
   * Compute and send feedback to the Mnemic Field.
   * This is the main entry point called after meditation completes.
   */
  async sendToMnemicField(mnemicField: MnemicField): Promise<FeedbackResult> {
    const feedback = this.computeFeedback()
    
    if (Object.keys(feedback).length === 0) {
      return {
        sessionId: this.sessionId,
        engramsTracked: 0,
        helpfulCount: 0,
        unhelpfulCount: 0,
        feedbackSent: false,
        reason: 'no engrams tracked',
      }
    }

    const helpfulCount = Object.values(feedback).filter(Boolean).length
    const unhelpfulCount = Object.values(feedback).filter(v => !v).length

    // Send feedback to Mnemic Field
    const success = mnemicField.recordEnrichFeedback(feedback)

    const result: FeedbackResult = {
      sessionId: this.sessionId,
      engramsTracked: this.retrieved.size,
      helpfulCount,
      unhelpfulCount,
      feedbackSent: success,
      reason: success ? 'feedback recorded' : 'failed to record feedback',
    }

    this.logger.info('[MeditationFeedback] Feedback sent to Mnemic Field', {
      ...result,
      helpfulRatio: (helpfulCount / Object.keys(feedback).length).toFixed(2),
    })

    return result
  }

  /** Get summary stats for this session */
  getStats(): FeedbackStats {
    const feedback = this.computeFeedback()
    const helpfulCount = Object.values(feedback).filter(Boolean).length
    const unhelpfulCount = Object.values(feedback).filter(v => !v).length

    return {
      retrievedCount: this.retrieved.size,
      usedCount: this.used.size,
      productiveCount: this.productive.size,
      unproductiveCount: this.unproductive.size,
      helpfulCount,
      unhelpfulCount,
      helpfulRatio: Object.keys(feedback).length > 0 
        ? helpfulCount / Object.keys(feedback).length 
        : 0,
    }
  }
}

export interface FeedbackResult {
  sessionId: string
  engramsTracked: number
  helpfulCount: number
  unhelpfulCount: number
  feedbackSent: boolean
  reason: string
}

export interface FeedbackStats {
  retrievedCount: number
  usedCount: number
  productiveCount: number
  unproductiveCount: number
  helpfulCount: number
  unhelpfulCount: number
  helpfulRatio: number
}
