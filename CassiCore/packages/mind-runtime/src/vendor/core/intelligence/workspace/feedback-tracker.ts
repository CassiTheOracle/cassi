/**
 * FeedbackTracker — Closes the GWT loop by detecting signal incorporation.
 *
 * After each turn, examines the LLM's response for evidence that
 * workspace signals were incorporated. Updates source credibility
 * in WorkspaceMemory, creating the learning feedback loop that makes
 * the workspace self-tuning.
 *
 * Detection is lightweight: keyword matching between signal content
 * and LLM response. Runs after turn completion, not on the critical path.
 *
 * Outcomes:
 *   incorporated — response references signal content/domain → credibility +0.03
 *   noted        — response acknowledges domain without acting → credibility +0.01
 *   ignored      — no relationship detected → credibility -0.01
 */

import type { CognitiveSignal } from './cognitive-signal.js'
import type { WorkspaceMemory, FeedbackOutcome } from './workspace-memory.js'
import { extractKeywords, keywordOverlap } from './luminance.js'


/** Minimum keyword overlap to consider a signal "incorporated" */
const INCORPORATED_THRESHOLD = 0.30

/** Minimum overlap for "noted" (acknowledged but not acted on) */
const NOTED_THRESHOLD = 0.15


export interface FeedbackResult {
  signalId: string
  source: string
  outcome: FeedbackOutcome
  overlapScore: number
}


export class FeedbackTracker {
  private memory: WorkspaceMemory

  constructor(memory: WorkspaceMemory) {
    this.memory = memory
  }


  /**
   * Analyze an LLM response against the signals that were in the workspace
   * during this turn. Returns feedback for each signal and updates credibility.
   */
  analyzeResponse(
    response: string,
    activeSignals: CognitiveSignal[],
  ): FeedbackResult[] {
    if (!response || activeSignals.length === 0) return []

    const responseKeywords = extractKeywords(response)
    if (responseKeywords.size === 0) return []

    const results: FeedbackResult[] = []

    for (const signal of activeSignals) {
      const signalKeywords = extractKeywords(signal.content)
      const overlap = keywordOverlap(signalKeywords, responseKeywords)

      let outcome: FeedbackOutcome
      if (overlap >= INCORPORATED_THRESHOLD) {
        outcome = 'incorporated'
      } else if (overlap >= NOTED_THRESHOLD) {
        outcome = 'noted'
      } else {
        outcome = 'ignored'
      }

      this.memory.applyFeedback(signal.source, outcome)

      results.push({
        signalId: signal.signalId,
        source: signal.source,
        outcome,
        overlapScore: overlap,
      })
    }

    return results
  }
}
