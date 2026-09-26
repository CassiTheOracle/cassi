/**
 * Locus — Global Workspace for Constellation
 *
 * The Locus is the capacity-limited attentional workspace sitting between
 * the Corpus (strategic organizer) and the Brainstems (local processors).
 * It implements Global Workspace Theory: only the most salient cross-branch
 * content gets broadcast globally.
 *
 * Four-stage pipeline per Corpus sweep:
 *   1. SparkExtractor diffs digests → produces Sparks
 *   2. KindlingEngine scores Sparks → fills Focus slots (memory-informed)
 *   3. Radiance broadcasts kindled content → injects into all branches
 *   4. Memory feedback loop: kindlings create memories, responses update them
 *
 * The three memory integration points form a feedback loop:
 *   Memory → informs Luminance → kindles → writes Memory → branches respond → updates Memory
 *
 * Named after the locus coeruleus — the brainstem nucleus that modulates
 * attention and arousal across the entire cortex.
 */

import type { ILogger } from '../vendor/types/interfaces.js'
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
import { LocusMemory } from './constellation-memory.js'
import type { LocusMemoryPersistence } from './constellation-memory.js'
import type { LocusMemoryConfig, LocusMemoryStats, MemoryFeedback } from './memory-types.js'
import { DEFAULT_MEMORY_CONFIG } from './memory-types.js'


export interface LocusDeps {
  logger: ILogger
  config?: LocusConfig
  memoryConfig?: LocusMemoryConfig
  memoryPersistence?: LocusMemoryPersistence
  /** Current constellation session ID (for memory provenance) */
  sessionId?: string
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
  /** Memory feedback from radiance responses (closes the loop) */
  memoryFeedback: MemoryFeedback[]
  /** Memories created from kindling events */
  memoriesWritten: number
}


export class Locus {
  private config: LocusConfig
  private logger: ILogger
  private sparkExtractor: SparkExtractor
  private kindlingEngine: KindlingEngine
  private radiance: Radiance
  private memory: LocusMemory
  private sessionId: string

  /**
   * Maps radianceId → source spark content, for memory feedback matching.
   * Built during broadcast, consumed during response tracking.
   */
  private radianceSourceContent = new Map<string, string>()

  constructor(deps: LocusDeps) {
    this.config = deps.config ?? DEFAULT_LOCUS_CONFIG
    this.logger = deps.logger.child?.('locus') ?? deps.logger
    this.sessionId = deps.sessionId ?? 'unknown'

    this.sparkExtractor = new SparkExtractor({ logger: this.logger })
    this.kindlingEngine = new KindlingEngine({ logger: this.logger, config: this.config })
    this.radiance = new Radiance({ logger: this.logger, config: this.config })
    this.memory = new LocusMemory({
      logger: this.logger,
      config: deps.memoryConfig ?? DEFAULT_MEMORY_CONFIG,
      persistence: deps.memoryPersistence,
    })

    this.logger.info('Locus initialized', {
      foci: this.config.foci,
      kindlingThreshold: this.config.kindlingThreshold,
      enabled: this.config.enabled,
      memoryLoaded: this.memory.getActive().length,
    })
  }

  /**
   * Run a single Locus sweep. Called by the Corpus each sweep cycle.
   *
   * Pipeline:
   *   1. Extract Sparks from digest changes
   *   2. Score and compete for Focus slots (memory modulates luminance)
   *   3. Broadcast kindled content to all branches (radiance)
   *   4. Write memories from kindled sparks (write gate)
   *   5. Track responses from previous broadcasts
   *   6. Feed responses back into memory (closes the loop)
   *   7. Idle decay on memories not being recalled
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
      return {
        sparksExtracted: 0, kindlingEvents: [], radianceEvents: [],
        responses: [], memoryFeedback: [], memoriesWritten: 0,
      }
    }

    const { crossPatterns, topology, assessments, injectGuidance } = options

    // 1. Extract Sparks from digest diffs
    const sparks = this.sparkExtractor.extract(currentDigests, crossPatterns)

    // 2. Score and compete for Focus slots (memory-informed luminance)
    const kindlingEvents = this.kindlingEngine.evaluate(
      sparks, currentDigests, topology, assessments, this.memory,
    )

    // 3. Broadcast kindled content
    let radianceEvents: RadianceEvent[] = []
    if (injectGuidance && kindlingEvents.length > 0) {
      radianceEvents = this.radiance.broadcast(
        kindlingEvents, activeHelixIds, topology, injectGuidance, currentDigests, assessments,
      )

      // Track radiance → spark content mapping for memory feedback
      for (const event of radianceEvents) {
        this.radianceSourceContent.set(event.radianceId, event.source.spark.content)
      }
    }

    // 4. Write memories from kindled sparks (write gate)
    let memoriesWritten = 0
    for (const event of kindlingEvents) {
      this.memory.write(event, this.sessionId)
      memoriesWritten++
    }

    // 5. Track responses from previous broadcasts
    let responses: RadianceResponse[] = []
    if (assessments) {
      responses = this.radiance.trackResponses(currentDigests, assessments)
    }

    // 6. Feed responses back into memory (closes the loop)
    let memoryFeedback: MemoryFeedback[] = []
    if (responses.length > 0) {
      memoryFeedback = this.memory.applyFeedback(responses, this.radianceSourceContent)
    }

    // 7. Idle decay
    this.memory.decayIdle()

    if (sparks.length > 0 || kindlingEvents.length > 0) {
      const memStats = this.memory.getStats()
      this.logger.info('Locus sweep complete', {
        sparks: sparks.length,
        kindled: kindlingEvents.length,
        broadcast: radianceEvents.length,
        responses: responses.length,
        memoryFeedback: memoryFeedback.length,
        memoriesWritten,
        fociOccupied: this.kindlingEngine.getFoci().filter(f => f.spark !== null).length,
        activeMemories: memStats.totalMemories - memStats.byPhase.invalidated,
        avgConfidence: memStats.avgConfidence.toFixed(3),
      })
    }

    return {
      sparksExtracted: sparks.length,
      kindlingEvents,
      radianceEvents,
      responses,
      memoryFeedback,
      memoriesWritten,
    }
  }

  /**
   * Consolidate memories at the end of a constellation run.
   * Provisional → confirmed → consolidated, or invalidated.
   */
  consolidateMemory(): { promoted: number; invalidated: number } {
    return this.memory.consolidate()
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
      memory: this.memory.getStats(),
      snapshotAt: Date.now(),
    }
  }

  /**
   * Get memory stats for external consumption (Corpus, training pipeline).
   */
  getMemoryStats(): LocusMemoryStats {
    return this.memory.getStats()
  }

  /**
   * Direct access to memory for testing and introspection.
   */
  getMemory(): LocusMemory {
    return this.memory
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
    this.memory.reset()
    this.radianceSourceContent.clear()
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

export type {
  LocusMemoryEntry,
  LocusMemoryConfig,
  LocusMemoryStats,
  MemoryPhase,
  MemoryFeedback,
  MemoryRecall,
} from './memory-types.js'

export { DEFAULT_MEMORY_CONFIG } from './memory-types.js'

export { SparkExtractor } from './spark-extractor.js'
export { KindlingEngine } from './kindling-engine.js'
export { Radiance } from './radiance.js'
export { LocusMemory } from './constellation-memory.js'
export type { LocusMemoryPersistence } from './constellation-memory.js'
export { GraphAttentionBridge } from './graph-attention-bridge.js'
export type { AttentionBridgeConfig, AttentionContext } from './graph-attention-bridge.js'
export { MnemicLocusMemoryPersistence } from './mnemic-locus-memory-persistence.js'
