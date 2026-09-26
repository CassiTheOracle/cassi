/**
 * HelixMetrics — Simple metrics tracker for Helix sessions.
 *
 * Tracks: work units produced, nudges sent, per-reviewer iteration counts,
 * and session duration.
 */

import type { ILogger } from '@cassicore/foundation'

export interface HelixMetricsSnapshot {
  workUnitsProduced: number
  nudgesSent: number
  reviewerIterations: {
    yang: number
    yin: number
  }
  sessionDurationMs: number
}

export class HelixMetrics {
  private workUnitsProduced = 0
  private nudgesSent = 0
  private reviewerIterations = { yang: 0, yin: 0 }
  private sessionStartTime: number

  constructor(private logger: ILogger) {
    this.sessionStartTime = Date.now()
  }

  incrementWorkUnits(): void {
    this.workUnitsProduced++
    this.logger.debug('Work unit produced', { count: this.workUnitsProduced })
  }

  incrementNudges(): void {
    this.nudgesSent++
    this.logger.debug('Nudge sent', { count: this.nudgesSent })
  }

  incrementReviewerIteration(reviewer: 'yang' | 'yin'): void {
    this.reviewerIterations[reviewer]++
    this.logger.debug(`${reviewer} iteration`, { count: this.reviewerIterations[reviewer] })
  }

  getSnapshot(): HelixMetricsSnapshot {
    return {
      workUnitsProduced: this.workUnitsProduced,
      nudgesSent: this.nudgesSent,
      reviewerIterations: { ...this.reviewerIterations },
      sessionDurationMs: Date.now() - this.sessionStartTime
    }
  }
}
