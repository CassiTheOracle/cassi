/**
 * Locus — Global Workspace for Constellation
 *
 * The Locus is the capacity-limited attentional workspace sitting between
 * the Corpus (strategic organizer) and the Brainstems (local processors).
 * It implements Global Workspace Theory: only the most salient cross-branch
 * content gets broadcast globally.
 *
 * Three-stage pipeline per Corpus sweep:
 *   1. SparkExtractor diffs digests → produces Sparks
 *   2. KindlingEngine scores Sparks → fills Focus slots (capacity-limited)
 *   3. Radiance broadcasts kindled content → injects into all branches
 *
 * The Locus facade wires the three together and provides a single sweep()
 * method for the Corpus to call.
 *
 * Named after the locus coeruleus — the brainstem nucleus that modulates
 * attention and arousal across the entire cortex.
 */

import type { ILogger } from '../../../../types/interfaces.js'
import type { BranchDigest, BranchAssessment, CrossHelixPattern } from '../corpus-types.js'
import type {
  LocusConfig,
  LocusTopologyAccessor,
  GuidanceInjector,
  LocusSnapshot,
  KindlingEvent,
  RadianceEvent,
  RadianceResponse,
} from './locus-types.js'
import { DEFAULT_LOCUS_CONFIG } from './locus-types.js'
import { SparkExtractor } from './spark-extractor.js'
import { KindlingEngine } from './kindling-engine.js'
import { Radiance } from './radiance.js'


export interface LocusDeps {
  logger: ILogger
  config?: LocusConfig
}

/**
 * Result of a single Locus sweep.
 */
export interface LocusSweepResult {
  /** Sparks extracted from digest diffs */
  sparksExtracted: number
  /** Sparks that made it into focus slots */
  kindlingEvents: KindlingEvent[]
  /** Broadcasts sent to branches */
  radianceEvents: RadianceEvent[]
  /** Tracked responses from previous broadcasts */
  responses: RadianceResponse[]
}


export class Locus {
  private config: LocusConfig
  private logger: ILogger
  private sparkExtractor: SparkExtractor
  private kindlingEngine: KindlingEngine
  private radiance: Radiance

  constructor(deps: LocusDeps) {
    this.config = deps.config ?? DEFAULT_LOCUS_CONFIG
    this.logger = deps.logger.child?.('locus') ?? deps.logger

    this.sparkExtractor = new SparkExtractor({ logger: this.logger })
    this.kindlingEngine = new KindlingEngine({ logger: this.logger, config: this.config })
    this.radiance = new Radiance({ logger: this.logger, config: this.config })

    this.logger.info('Locus initialized', {
      foci: this.config.foci,
      kindlingThreshold: this.config.kindlingThreshold,
      enabled: this.config.enabled,
    })
  }

  /**
   * Run a single Locus sweep. Called by the Corpus each sweep cycle.
   *
   * Pipeline:
   *   1. Extract Sparks from digest changes
   *   2. Score and compete for Focus slots (kindling)
   *   3. Broadcast kindled content to all branches (radiance)
   *   4. Track responses from previous broadcasts
   */
  sweep(
    currentDigests: BranchDigest[],
    activeHelixIds: string[],
    options: {
      crossPatterns?: CrossHelixPattern[]
      topology?: LocusTopologyAccessor
      assessments?: Map<string, BranchAssessment>
      injectGuidance?: GuidanceInjector
    } = {},
  ): LocusSweepResult {
    if (!this.config.enabled) {
      return { sparksExtracted: 0, kindlingEvents: [], radianceEvents: [], responses: [] }
    }

    const { crossPatterns, topology, assessments, injectGuidance } = options

    // 1. Extract Sparks from digest diffs
    const sparks = this.sparkExtractor.extract(currentDigests, crossPatterns)

    // 2. Score and compete for Focus slots
    const kindlingEvents = this.kindlingEngine.evaluate(
      sparks, currentDigests, topology, assessments,
    )

    // 3. Broadcast kindled content
    let radianceEvents: RadianceEvent[] = []
    if (injectGuidance && kindlingEvents.length > 0) {
      radianceEvents = this.radiance.broadcast(
        kindlingEvents, activeHelixIds, topology, injectGuidance, currentDigests, assessments,
      )
    }

    // 4. Track responses from previous broadcasts
    let responses: RadianceResponse[] = []
    if (assessments) {
      responses = this.radiance.trackResponses(currentDigests, assessments)
    }

    if (sparks.length > 0 || kindlingEvents.length > 0) {
      this.logger.info('Locus sweep complete', {
        sparks: sparks.length,
        kindled: kindlingEvents.length,
        broadcast: radianceEvents.length,
        responses: responses.length,
        fociOccupied: this.kindlingEngine.getFoci().filter(f => f.spark !== null).length,
      })
    }

    return {
      sparksExtracted: sparks.length,
      kindlingEvents,
      radianceEvents,
      responses,
    }
  }

  /**
   * Notify the Locus that a Helix has been deregistered.
   */
  removeHelix(helixId: string): void {
    this.sparkExtractor.removeHelix(helixId)
    this.kindlingEngine.removeHelix(helixId)
  }

  /**
   * Get a full snapshot of the Locus state.
   */
  getSnapshot(): LocusSnapshot {
    const stats = this.kindlingEngine.getStats()

    return {
      foci: this.kindlingEngine.getFoci(),
      recentKindlings: this.kindlingEngine.getKindlingHistory().slice(-20),
      recentRadiances: this.radiance.getRadianceHistory().slice(-20),
      recentResponses: this.radiance.getResponseHistory().slice(-20),
      totalSparksProcessed: stats.totalSparksProcessed,
      totalKindlings: stats.totalKindlings,
      totalRadiances: this.radiance.getTotalRadiances(),
      kindlingRate: stats.kindlingRate,
      snapshotAt: Date.now(),
    }
  }

  /**
   * Whether the Locus is enabled.
   */
  get enabled(): boolean {
    return this.config.enabled
  }

  /**
   * Reset all state (for testing).
   */
  reset(): void {
    this.sparkExtractor.reset()
    this.kindlingEngine.reset()
    this.radiance.reset()
  }
}


// Re-export types and defaults for convenience
export type {
  LocusConfig,
  LocusSnapshot,
  LocusTopologyAccessor,
  GuidanceInjector,
  Spark,
  SparkType,
  LuminanceScore,
  LuminanceWeights,
  Focus,
  KindlingEvent,
  EclipseEvent,
  RadianceEvent,
  RadianceResponse,
  RadianceResponseType,
} from './locus-types.js'

export {
  DEFAULT_LOCUS_CONFIG,
  DEFAULT_LUMINANCE_WEIGHTS,
} from './locus-types.js'

export { SparkExtractor } from './spark-extractor.js'
export { KindlingEngine } from './kindling-engine.js'
export { Radiance } from './radiance.js'
