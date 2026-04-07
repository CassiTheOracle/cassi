/**
 * Kindling Engine — Salience scoring, competition, and workspace management
 *
 * The core GWT mechanism. Evaluates Sparks by Luminance (composite salience),
 * filters dim sparks (below threshold), and manages the competitive process
 * where bright sparks claim Focus slots in the Locus workspace.
 *
 * The kindling metaphor: a spark must be bright enough to catch fire.
 * Once kindled, it occupies a Focus slot until it naturally dims (occupancy
 * decay) or is eclipsed by a brighter spark.
 *
 * Scoring uses topology distances for cross-relevance: a discovery from
 * a branch at the center of a cluster has higher cross-relevance than
 * one from an isolated branch.
 */

import type { ILogger } from '../../../../types/interfaces.js'
import type { BranchDigest, BranchAssessment } from '../corpus-types.js'
import type {
  Spark,
  SparkType,
  LuminanceScore,
  Focus,
  KindlingEvent,
  EclipseEvent,
  LocusConfig,
  LocusTopologyAccessor,
} from './locus-types.js'
import { DEFAULT_LOCUS_CONFIG } from './locus-types.js'
import type { LocusMemory } from './constellation-memory.js'
import type { MemoryRecall } from './memory-types.js'

let eventCounter = 0
function nextEventId(): string {
  return `kindle-${++eventCounter}-${Date.now().toString(36)}`
}

/**
 * Base urgency scores by spark type.
 * Blockers and tensions are inherently more urgent than discoveries.
 */
const BASE_URGENCY: Record<SparkType, number> = {
  blocker: 0.85,
  tension: 0.75,
  breakthrough: 0.6,
  convergence: 0.55,
  decision: 0.5,
  discovery: 0.35,
}

/**
 * Base novelty scores by spark type.
 * Discoveries and breakthroughs are inherently more novel.
 */
const BASE_NOVELTY: Record<SparkType, number> = {
  discovery: 0.8,
  breakthrough: 0.75,
  convergence: 0.6,
  tension: 0.55,
  decision: 0.45,
  blocker: 0.4,
}


export interface KindlingEngineDeps {
  logger: ILogger
  config?: LocusConfig
}

export class KindlingEngine {
  private foci: Focus[]
  private config: LocusConfig
  private logger: ILogger
  private kindlingHistory: KindlingEvent[] = []
  private totalSparksProcessed = 0
  private totalKindlings = 0

  constructor(deps: KindlingEngineDeps) {
    this.config = deps.config ?? DEFAULT_LOCUS_CONFIG
    this.logger = deps.logger.child?.('kindling-engine') ?? deps.logger

    this.foci = Array.from({ length: this.config.foci }, (_, i) => ({
      slotIndex: i,
      spark: null,
      occupiedSince: null,
      occupancyTicks: 0,
    }))

    this.logger.info('KindlingEngine initialized', {
      foci: this.config.foci,
      kindlingThreshold: this.config.kindlingThreshold,
    })
  }

  /**
   * Evaluate a batch of Sparks from the current sweep.
   * Returns KindlingEvents for sparks that won Focus slots.
   *
   * Algorithm:
   * 1. Score all sparks (compute luminance)
   * 2. Filter dim sparks (below kindling threshold)
   * 3. Sort by composite luminance (brightest first)
   * 4. For each spark, try to claim a focus:
   *    a. Empty focus → kindle (fill it)
   *    b. All foci occupied → compare with dimmest occupant
   *       - If spark > dimmest + eclipse margin → eclipse (displace)
   *       - Otherwise → stays dim (local to branch)
   * 5. Decay occupancy ticks on retained foci
   */
  evaluate(
    sparks: Spark[],
    allDigests: BranchDigest[],
    topology?: LocusTopologyAccessor,
    assessments?: Map<string, BranchAssessment>,
    memory?: LocusMemory,
  ): KindlingEvent[] {
    if (!this.config.enabled) return []

    const now = Date.now()
    this.totalSparksProcessed += sparks.length

    // Always decay occupancy, even if there are no new sparks this sweep
    this.decayOccupants()

    if (sparks.length === 0) return []

    // 1. Score all sparks
    for (const spark of sparks) {
      spark.luminance = this.scoreLuminance(spark, allDigests, topology, assessments, memory)
    }

    // 2. Filter dim sparks
    const brightSparks = sparks.filter(s => s.luminance.composite >= this.config.kindlingThreshold)
    const dimCount = sparks.length - brightSparks.length

    if (dimCount > 0) {
      this.logger.info('Dim sparks filtered', {
        total: sparks.length,
        bright: brightSparks.length,
        dim: dimCount,
        threshold: this.config.kindlingThreshold,
      })
    }

    // 3. Sort by composite luminance (brightest first)
    brightSparks.sort((a, b) => b.luminance.composite - a.luminance.composite)

    // 4. Competition for focus slots
    const events: KindlingEvent[] = []

    for (const spark of brightSparks) {
      // Skip if this branch already has a spark in a focus (one focus per branch)
      if (this.foci.some(f => f.spark?.sourceHelixId === spark.sourceHelixId)) continue

      const event = this.tryKindle(spark, now)
      if (event) {
        events.push(event)
        this.totalKindlings++
      }
    }

    if (events.length > 0) {
      this.kindlingHistory.push(...events)
      this.trimHistory()

      this.logger.info('Kindling events', {
        kindled: events.length,
        eclipses: events.filter(e => e.eclipse !== null).length,
        fociOccupied: this.foci.filter(f => f.spark !== null).length,
      })
    }

    return events
  }

  /**
   * Get current state of all foci.
   */
  getFoci(): Focus[] {
    return this.foci.map(f => ({ ...f }))
  }

  /**
   * Get kindling history (for training data export).
   */
  getKindlingHistory(): KindlingEvent[] {
    return [...this.kindlingHistory]
  }

  /**
   * Get stats for snapshot.
   */
  getStats(): { totalSparksProcessed: number; totalKindlings: number; kindlingRate: number } {
    return {
      totalSparksProcessed: this.totalSparksProcessed,
      totalKindlings: this.totalKindlings,
      kindlingRate: this.totalSparksProcessed > 0
        ? this.totalKindlings / this.totalSparksProcessed
        : 0,
    }
  }

  /**
   * Remove a specific Helix's spark from any focus it occupies.
   */
  removeHelix(helixId: string): void {
    for (const focus of this.foci) {
      if (focus.spark?.sourceHelixId === helixId) {
        focus.spark = null
        focus.occupiedSince = null
        focus.occupancyTicks = 0
      }
    }
  }

  /**
   * Reset all state (for testing).
   */
  reset(): void {
    for (const focus of this.foci) {
      focus.spark = null
      focus.occupiedSince = null
      focus.occupancyTicks = 0
    }
    this.kindlingHistory = []
    this.totalSparksProcessed = 0
    this.totalKindlings = 0
    eventCounter = 0
  }

  // --- Private ---

  /**
   * Try to kindle a spark into a focus slot.
   * Returns a KindlingEvent if successful, null if all foci are too bright.
   */
  private tryKindle(spark: Spark, now: number): KindlingEvent | null {
    // Try to find an empty focus first
    const emptyFocus = this.foci.find(f => f.spark === null)
    if (emptyFocus) {
      emptyFocus.spark = spark
      emptyFocus.occupiedSince = now
      emptyFocus.occupancyTicks = 0

      return {
        eventId: nextEventId(),
        spark,
        slotIndex: emptyFocus.slotIndex,
        eclipse: null,
        kindlingLuminance: spark.luminance.composite,
        timestamp: now,
      }
    }

    // All foci occupied — try to eclipse the dimmest
    const dimmestFocus = this.findDimmestFocus()
    if (!dimmestFocus || !dimmestFocus.spark) return null

    const effectiveLuminance = this.effectiveLuminance(dimmestFocus)
    if (spark.luminance.composite > effectiveLuminance + this.config.eclipseMargin) {
      const eclipsedSpark = dimmestFocus.spark
      const eclipseEvent: EclipseEvent = {
        eclipsedSpark,
        eclipsingSpark: spark,
        luminanceDelta: spark.luminance.composite - effectiveLuminance,
        occupancyAtEclipse: dimmestFocus.occupancyTicks,
      }

      dimmestFocus.eclipsedSparkId = eclipsedSpark.sparkId
      dimmestFocus.spark = spark
      dimmestFocus.occupiedSince = now
      dimmestFocus.occupancyTicks = 0

      return {
        eventId: nextEventId(),
        spark,
        slotIndex: dimmestFocus.slotIndex,
        eclipse: eclipseEvent,
        kindlingLuminance: spark.luminance.composite,
        timestamp: now,
      }
    }

    return null
  }

  /**
   * Find the focus with the lowest effective luminance.
   */
  private findDimmestFocus(): Focus | null {
    let dimmest: Focus | null = null
    let lowestLuminance = Infinity

    for (const focus of this.foci) {
      if (!focus.spark) continue
      const eff = this.effectiveLuminance(focus)
      if (eff < lowestLuminance) {
        lowestLuminance = eff
        dimmest = focus
      }
    }

    return dimmest
  }

  /**
   * Compute effective luminance for a focus occupant.
   * Decays with occupancy: the longer a spark sits, the dimmer it gets,
   * making it easier to eclipse.
   */
  private effectiveLuminance(focus: Focus): number {
    if (!focus.spark) return 0

    const baseLuminance = focus.spark.luminance.composite
    if (focus.occupancyTicks <= 0) return baseLuminance

    // Linear decay: lose 10% of luminance per tick, min 20% of original
    const decayFactor = Math.max(0.2, 1.0 - (focus.occupancyTicks * 0.1))
    return baseLuminance * decayFactor
  }

  /**
   * Increment occupancy ticks on all occupied foci.
   * Foci that exceed maxOccupancyTicks are cleared (natural expiry).
   */
  private decayOccupants(): void {
    for (const focus of this.foci) {
      if (focus.spark) {
        focus.occupancyTicks++
        if (focus.occupancyTicks > this.config.maxOccupancyTicks) {
          this.logger.info('Focus expired', {
            slotIndex: focus.slotIndex,
            sparkId: focus.spark.sparkId,
            ticks: focus.occupancyTicks,
          })
          focus.spark = null
          focus.occupiedSince = null
          focus.occupancyTicks = 0
        }
      }
    }
  }

  /**
   * Score a spark's luminance (composite salience).
   *
   * Components:
   *   novelty: base type novelty + content length heuristic + memory modulation
   *   urgency: base type urgency + blocker severity
   *   crossRelevance: topology-based — avg similarity from source to all other branches
   *   qualityDelta: branch quality trajectory (from assessment or confidence level)
   *
   * Memory integration (option B): when memories exist for similar content,
   * novelty is modulated. Confirming memories reduce novelty ("we know this"),
   * contradicting memories boost it ("this challenges what we knew").
   */
  private scoreLuminance(
    spark: Spark,
    allDigests: BranchDigest[],
    topology?: LocusTopologyAccessor,
    assessments?: Map<string, BranchAssessment>,
    memory?: LocusMemory,
  ): LuminanceScore {
    const w = this.config.luminanceWeights

    // Novelty: base + content richness heuristic (longer = potentially more novel)
    const baseNovelty = BASE_NOVELTY[spark.type]
    const contentRichness = Math.min(spark.content.length / 200, 1.0) * 0.2
    let novelty = Math.min(baseNovelty + contentRichness, 1.0)

    // Memory modulation: existing memories shift novelty
    let memoryRecalls: MemoryRecall[] | undefined
    if (memory) {
      memoryRecalls = memory.recall(spark)
      if (memoryRecalls.length > 0) {
        let totalModulation = 0
        for (const recall of memoryRecalls) {
          totalModulation += recall.noveltyModulation
        }
        novelty = Math.max(0, Math.min(1.0, novelty + totalModulation))
      }
    }

    // Urgency: base type urgency
    const urgency = BASE_URGENCY[spark.type]

    // Cross-relevance: how many other branches would benefit?
    let crossRelevance = 0.5 // default if no topology
    if (topology && allDigests.length > 1) {
      const otherIds = allDigests
        .filter(d => d.helixId !== spark.sourceHelixId)
        .map(d => d.helixId)

      if (otherIds.length > 0) {
        let totalSimilarity = 0
        for (const otherId of otherIds) {
          totalSimilarity += topology.getSimilarity(spark.sourceHelixId, otherId)
        }
        crossRelevance = totalSimilarity / otherIds.length
      }
    }

    // Quality delta: branch trajectory
    let qualityDelta = 0
    const assessment = assessments?.get(spark.sourceHelixId)
    if (assessment && assessment.scoreTrajectory.length >= 2) {
      const traj = assessment.scoreTrajectory
      const recent = traj[traj.length - 1]
      const prev = traj[traj.length - 2]
      qualityDelta = Math.max(-1, Math.min(1, (recent - prev) * 5)) // amplify small deltas
    }

    // Composite: weighted sum, normalized qualityDelta to 0-1 range for weighting
    const normalizedQD = (qualityDelta + 1) / 2
    const composite = (
      w.novelty * novelty +
      w.urgency * urgency +
      w.crossRelevance * crossRelevance +
      w.qualityDelta * normalizedQD
    )

    return {
      novelty,
      urgency,
      crossRelevance,
      qualityDelta,
      composite: Math.min(composite, 1.0),
    }
  }

  /**
   * Trim event history to configured maximum.
   */
  private trimHistory(): void {
    if (this.kindlingHistory.length > this.config.maxEventHistory) {
      this.kindlingHistory = this.kindlingHistory.slice(-this.config.maxEventHistory)
    }
  }
}
