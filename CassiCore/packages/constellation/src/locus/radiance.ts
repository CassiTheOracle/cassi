/**
 * Radiance — Global broadcast of kindled Locus content
 *
 * When a Spark kindles (enters the Locus workspace), Radiance broadcasts
 * it to ALL active Helix branches via guidance injection. This is the
 * GWT "global broadcast" — workspace content radiating to all processors.
 *
 * Each broadcast includes topology distance from source to recipient,
 * so the receiving Brainstem can gauge relevance to its own work.
 *
 * Response tracking: after broadcasting, subsequent sweeps check if
 * branches changed behavior, incorporated findings, or contradicted
 * the broadcast. This creates a feedback loop for training.
 */

import type { ILogger } from '../vendor/types/interfaces.js'
import type { BranchDigest, BranchAssessment } from '../corpus-types.js'
import type {
  KindlingEvent,
  RadianceEvent,
  RadianceResponse,
  RadianceResponseType,
  LocusTopologyAccessor,
  GuidanceInjector,
  LocusConfig,
} from './locus-types.js'
import { DEFAULT_LOCUS_CONFIG } from './locus-types.js'

let radianceCounter = 0
function nextRadianceId(): string {
  return `radiance-${++radianceCounter}-${Date.now().toString(36)}`
}


export interface RadianceDeps {
  logger: ILogger
  config?: LocusConfig
}

export class Radiance {
  private radianceHistory: RadianceEvent[] = []
  private responseHistory: RadianceResponse[] = []
  private totalRadiances = 0
  private logger: ILogger
  private config: LocusConfig

  /**
   * Track branch state at broadcast time for response detection.
   * Maps radianceId → helixId → snapshot of key metrics at broadcast time.
   */
  private broadcastSnapshots = new Map<string, Map<string, BroadcastSnapshot>>()

  constructor(deps: RadianceDeps) {
    this.config = deps.config ?? DEFAULT_LOCUS_CONFIG
    this.logger = deps.logger.child?.('radiance') ?? deps.logger
  }

  /**
   * Broadcast kindled content to all active Helix branches.
   *
   * Returns RadianceEvents for each kindling that was broadcast.
   * The injectGuidance function delivers the content into each branch's
   * Brainstem guidance queue.
   */
  broadcast(
    kindlingEvents: KindlingEvent[],
    activeHelixIds: string[],
    topology: LocusTopologyAccessor | undefined,
    injectGuidance: GuidanceInjector,
    currentDigests?: BranchDigest[],
    assessments?: Map<string, BranchAssessment>,
  ): RadianceEvent[] {
    if (kindlingEvents.length === 0 || activeHelixIds.length === 0) return []

    const now = Date.now()
    const events: RadianceEvent[] = []

    for (const kindling of kindlingEvents) {
      const sourceId = kindling.spark.sourceHelixId
      const recipients = activeHelixIds.filter(id => id !== sourceId)

      if (recipients.length === 0) continue

      // Compute per-recipient topology distances
      const recipientDistances: Record<string, number> = {}
      for (const recipientId of recipients) {
        recipientDistances[recipientId] = topology
          ? topology.getDistance(sourceId, recipientId)
          : 1.0 // default distance if no topology
      }

      // Format broadcast content
      const content = this.formatBroadcast(kindling, recipientDistances)

      // Inject guidance into all recipients
      for (const recipientId of recipients) {
        const distance = recipientDistances[recipientId]
        const urgency = this.urgencyFromKindling(kindling, distance)
        injectGuidance(recipientId, content, urgency)
      }

      const radianceEvent: RadianceEvent = {
        radianceId: nextRadianceId(),
        source: kindling,
        content,
        recipients,
        recipientDistances,
        timestamp: now,
      }

      events.push(radianceEvent)
      this.totalRadiances++

      // Snapshot branch state for response detection
      if (currentDigests || assessments) {
        const snapshots = new Map<string, BroadcastSnapshot>()
        for (const recipientId of recipients) {
          const digest = currentDigests?.find(d => d.helixId === recipientId)
          const assessment = assessments?.get(recipientId)
          snapshots.set(recipientId, {
            rollingScore: assessment?.rollingScore ?? digest?.rollingScore ?? 0,
            keyFindingsCount: digest?.keyFindings?.length ?? 0,
            approach: digest?.approach ?? 'exploration',
            scoreTrajectoryLast: assessment?.scoreTrajectory?.slice(-3) ?? [],
          })
        }
        this.broadcastSnapshots.set(radianceEvent.radianceId, snapshots)
      }
    }

    if (events.length > 0) {
      this.radianceHistory.push(...events)
      this.trimHistory()

      this.logger.info('Radiance broadcast', {
        broadcasts: events.length,
        totalRecipients: events.reduce((sum, e) => sum + e.recipients.length, 0),
      })
    }

    return events
  }

  /**
   * Track responses to previous broadcasts by comparing current branch state
   * to the state at broadcast time.
   *
   * Called on subsequent sweeps. Detects whether branches incorporated,
   * noted, ignored, or contradicted the broadcast.
   */
  trackResponses(
    currentDigests: BranchDigest[],
    assessments: Map<string, BranchAssessment>,
  ): RadianceResponse[] {
    const responses: RadianceResponse[] = []
    const now = Date.now()
    const digestMap = new Map(currentDigests.map(d => [d.helixId, d]))

    // Process recent radiance events that we haven't fully tracked yet
    const recentRadiances = this.radianceHistory.slice(-20)

    for (const radiance of recentRadiances) {
      const snapshots = this.broadcastSnapshots.get(radiance.radianceId)
      if (!snapshots) continue

      // Only track responses after at least 1 sweep (give branches time to react)
      const sweepsSinceBroadcast = Math.floor((now - radiance.timestamp) / 10_000) // ~10s per sweep
      if (sweepsSinceBroadcast < 1) continue

      // Already tracked?
      const alreadyTracked = this.responseHistory.some(r => r.radianceId === radiance.radianceId)
      if (alreadyTracked) continue

      for (const recipientId of radiance.recipients) {
        const snapshot = snapshots.get(recipientId)
        if (!snapshot) continue

        const currentDigest = digestMap.get(recipientId)
        const currentAssessment = assessments.get(recipientId)

        const response = this.detectResponse(
          radiance, recipientId, snapshot, currentDigest, currentAssessment, sweepsSinceBroadcast, now,
        )
        if (response) {
          responses.push(response)
        }
      }

      // Clean up snapshot after tracking
      this.broadcastSnapshots.delete(radiance.radianceId)
    }

    if (responses.length > 0) {
      this.responseHistory.push(...responses)
      this.trimResponseHistory()

      this.logger.info('Radiance responses tracked', {
        count: responses.length,
        byType: this.countByType(responses),
      })
    }

    return responses
  }

  /**
   * Get radiance history (for training data export).
   */
  getRadianceHistory(): RadianceEvent[] {
    return [...this.radianceHistory]
  }

  /**
   * Get response history (for training data export).
   */
  getResponseHistory(): RadianceResponse[] {
    return [...this.responseHistory]
  }

  /**
   * Get stats for snapshot.
   */
  getTotalRadiances(): number {
    return this.totalRadiances
  }

  /**
   * Reset all state (for testing).
   */
  reset(): void {
    this.radianceHistory = []
    this.responseHistory = []
    this.broadcastSnapshots.clear()
    this.totalRadiances = 0
    radianceCounter = 0
  }

  // --- Private ---

  /**
   * Format broadcast content for injection.
   * Includes source context and the spark content.
   */
  private formatBroadcast(
    kindling: KindlingEvent,
    recipientDistances: Record<string, number>,
  ): string {
    const spark = kindling.spark
    const avgDistance = Object.values(recipientDistances).reduce((a, b) => a + b, 0) /
      (Object.values(recipientDistances).length || 1)

    const sections = [
      `[Locus Broadcast — ${spark.type}]`,
      `From: ${spark.sourceGoal}`,
      `Luminance: ${kindling.kindlingLuminance.toFixed(2)} | Cross-relevance: avg ${avgDistance.toFixed(2)} distance`,
      '',
      spark.content,
    ]

    if (spark.relevantFiles.length > 0) {
      sections.push('', `Related files: ${spark.relevantFiles.join(', ')}`)
    }

    if (kindling.eclipse) {
      sections.push('', `(Eclipsed: ${kindling.eclipse.eclipsedSpark.type} from ${kindling.eclipse.eclipsedSpark.sourceGoal})`)
    }

    return sections.join('\n')
  }

  /**
   * Determine guidance urgency based on kindling luminance and topology distance.
   * Closer branches (lower distance) get higher urgency.
   */
  private urgencyFromKindling(
    kindling: KindlingEvent,
    distance: number,
  ): 'low' | 'medium' | 'high' | 'critical' {
    const luminance = kindling.kindlingLuminance

    // Blockers and tensions with high luminance → medium/high
    if (kindling.spark.type === 'blocker' && luminance > 0.7) {
      return distance < 1.5 ? 'high' : 'medium'
    }
    if (kindling.spark.type === 'tension' && luminance > 0.6) {
      return distance < 1.5 ? 'medium' : 'low'
    }

    // Everything else → low (informational)
    return 'low'
  }

  /**
   * Detect how a branch responded to a broadcast by comparing pre/post state.
   */
  private detectResponse(
    radiance: RadianceEvent,
    recipientId: string,
    snapshot: BroadcastSnapshot,
    currentDigest: BranchDigest | undefined,
    currentAssessment: BranchAssessment | undefined,
    sweepsSinceBroadcast: number,
    now: number,
  ): RadianceResponse | null {
    if (!currentDigest && !currentAssessment) return null

    let responseType: RadianceResponseType = 'ignored'
    let evidence = ''

    const sparkContent = radiance.source.spark.content.toLowerCase()

    // Check if findings were incorporated
    if (currentDigest) {
      const newFindings = currentDigest.keyFindings?.filter(f =>
        f.toLowerCase().includes(sparkContent.substring(0, 30).toLowerCase()) ||
        sparkContent.includes(f.substring(0, 30).toLowerCase()),
      )
      if (newFindings && newFindings.length > 0) {
        responseType = 'incorporated'
        evidence = `Branch added related findings: ${newFindings[0]}`
      }
    }

    // Check approach change after broadcast
    if (responseType === 'ignored' && currentDigest && snapshot.approach !== currentDigest.approach) {
      responseType = 'noted'
      evidence = `Approach changed from ${snapshot.approach} to ${currentDigest.approach} after broadcast`
    }

    // Check score trajectory shift
    if (responseType === 'ignored' && currentAssessment) {
      const currentScore = currentAssessment.rollingScore
      const scoreDelta = currentScore - snapshot.rollingScore
      if (Math.abs(scoreDelta) > 0.1) {
        responseType = scoreDelta > 0 ? 'noted' : 'ignored'
        evidence = `Score shifted ${scoreDelta > 0 ? '+' : ''}${scoreDelta.toFixed(2)} after broadcast`
      }
    }

    return {
      helixId: recipientId,
      radianceId: radiance.radianceId,
      responseType,
      evidence,
      responseDelay: sweepsSinceBroadcast,
      timestamp: now,
    }
  }

  private countByType(responses: RadianceResponse[]): Record<string, number> {
    const counts: Record<string, number> = {}
    for (const r of responses) {
      counts[r.responseType] = (counts[r.responseType] || 0) + 1
    }
    return counts
  }

  private trimHistory(): void {
    if (this.radianceHistory.length > this.config.maxEventHistory) {
      this.radianceHistory = this.radianceHistory.slice(-this.config.maxEventHistory)
    }
  }

  private trimResponseHistory(): void {
    if (this.responseHistory.length > this.config.maxEventHistory * 2) {
      this.responseHistory = this.responseHistory.slice(-this.config.maxEventHistory)
    }
  }
}


/**
 * Snapshot of a branch's state at broadcast time.
 * Used for response detection.
 */
interface BroadcastSnapshot {
  rollingScore: number
  keyFindingsCount: number
  approach: string
  scoreTrajectoryLast: number[]
}
