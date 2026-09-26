/**
 * MnemicBridge — Connects meditation activity to spatial memory.
 *
 * Observes the CorpusTree for new annotations from meditation Helixes.
 * Extracts concepts, spikes related engrams, and optionally creates new
 * engrams and triggers consolidation. This shifts the potentiation
 * landscape, which implicitly influences what memory injection surfaces
 * for sibling Helixes — cross-pollination through spatial memory.
 */

import type { ILogger, IEventBus } from '../vendor/types/interfaces.js'
import type { MnemicField, SpikeCreate } from '@cassicore/mnemic-field'
import type { ICorpusTree } from '../corpus-types.js'
import type { BrainstemAnnotation } from '../vendor/helix/brainstem-types.js'
import { SelfAwarenessDetector } from './self-awareness-detector.js'
import type { SelfAwarenessDetection } from './self-awareness-detector.js'


export interface MnemicBridgeConfig {
  /** How often to poll the CorpusTree for new annotations (ms). Default: 10_000 */
  pollIntervalMs: number
  /** Spike magnitude for meditation activations. Default: 0.4 */
  spikeMagnitude: number
  /** Minimum search score to spike an engram. Default: 0.3 */
  minMatchScore: number
  /** Max engrams to spike per annotation. Default: 5 */
  maxSpikesPerAnnotation: number
}

const DEFAULT_CONFIG: MnemicBridgeConfig = {
  pollIntervalMs: 10_000,
  spikeMagnitude: 0.4,
  minMatchScore: 0.3,
  maxSpikesPerAnnotation: 5,
}


export class MnemicBridge {
  private field: MnemicField
  private tree: ICorpusTree
  private logger: ILogger
  private config: MnemicBridgeConfig

  private pollTimer?: NodeJS.Timeout
  private stepCursors = new Map<string, number>()
  private stopped = false

  /** Running totals for session reporting */
  private stats = { spiked: 0, created: 0, consolidations: 0 }

  /** Self-awareness detection — monitors explorers for self-recognition */
  private selfAwareness: SelfAwarenessDetector


  constructor(
    field: MnemicField,
    tree: ICorpusTree,
    logger: ILogger,
    config?: Partial<MnemicBridgeConfig>,
    eventBus?: IEventBus,
  ) {
    this.field = field
    this.tree = tree
    this.logger = logger.child ? logger.child('mnemic-bridge') : logger
    this.config = { ...DEFAULT_CONFIG, ...config }
    this.selfAwareness = new SelfAwarenessDetector(logger, eventBus)
  }


  start(): void {
    this.stopped = false
    this.pollTimer = setInterval(() => this.poll(), this.config.pollIntervalMs)
    this.pollTimer.unref()
    this.logger.info('MnemicBridge started', { pollIntervalMs: this.config.pollIntervalMs })
  }

  stop(): void {
    this.stopped = true
    if (this.pollTimer) {
      clearInterval(this.pollTimer)
      this.pollTimer = undefined
    }
    this.logger.info('MnemicBridge stopped', { stats: this.stats })
  }

  getStats(): { spiked: number; created: number; consolidations: number } {
    return { ...this.stats }
  }

  getSelfAwarenessDetections(): SelfAwarenessDetection[] {
    return this.selfAwareness.getDetections()
  }

  getSelfAwarenessCount(): number {
    return this.selfAwareness.getDetectionCount()
  }


  /**
   * Poll the CorpusTree for new annotations and spike related engrams.
   */
  private poll(): void {
    if (this.stopped) return

    try {
      const branches = this.tree.getAllBranches()

      for (const branch of branches) {
        const cursor = this.stepCursors.get(branch.helixId) ?? 0
        const newSteps = branch.steps.slice(cursor)

        for (const step of newSteps) {
          this.processAnnotation(step.annotation, branch.helixId)
        }

        if (newSteps.length > 0) {
          this.stepCursors.set(branch.helixId, branch.steps.length)
        }
      }

      // Self-awareness scan — check all new steps for self-recognition signals
      this.selfAwareness.scan(this.tree)
    } catch (err) {
      this.logger.warn('MnemicBridge poll failed', { error: String(err) })
    }
  }


  /**
   * Extract concepts from a Brainstem annotation and spike related engrams.
   */
  private processAnnotation(annotation: BrainstemAnnotation, helixId: string): void {
    const concepts = this.extractConcepts(annotation)
    if (concepts.length === 0) return

    const searchQuery = concepts.join(' ')

    try {
      const hits = this.field.searchText(searchQuery, this.config.maxSpikesPerAnnotation * 2)
      const relevant = hits.filter(h => h.score >= this.config.minMatchScore)

      let spikedCount = 0
      for (const hit of relevant.slice(0, this.config.maxSpikesPerAnnotation)) {
        const spike: SpikeCreate = {
          engramId: hit.engram.id,
          magnitude: this.config.spikeMagnitude,
          taskContext: `meditation:${helixId}`,
          outcome: 'unknown' as const,
        }
        this.field.spike(spike)
        spikedCount++
      }

      if (spikedCount > 0) {
        this.stats.spiked += spikedCount
        this.logger.debug('Spiked engrams from meditation annotation', {
          helixId,
          concepts: concepts.length,
          spiked: spikedCount,
        })
      }
    } catch (err) {
      this.logger.warn('Failed to process meditation annotation', { error: String(err) })
    }
  }


  /**
   * Extract meaningful concept strings from a Brainstem annotation.
   */
  private extractConcepts(annotation: BrainstemAnnotation): string[] {
    const concepts: string[] = []

    for (const discovery of annotation.discoveries) {
      if (discovery.length > 5) concepts.push(discovery)
    }

    if (annotation.knowledgeDelta && annotation.knowledgeDelta.length > 5) {
      concepts.push(annotation.knowledgeDelta)
    }

    if (annotation.hypothesis && annotation.hypothesis.length > 5) {
      concepts.push(annotation.hypothesis)
    }

    return concepts
  }


  /**
   * Store a new engram from Corpus synthesis during meditation.
   * Called by the Corpus when it identifies a genuine insight.
   */
  storeInsightEngram(content: string, tags?: string[]): string {
    const engram = this.field.store({
      content,
      nodeType: 'pattern',
      provenance: 'meditation',
      tags: tags ?? ['meditation'],
    })
    this.stats.created++
    this.logger.info('Created meditation engram', { id: engram.id, content: content.slice(0, 80) })
    return engram.id
  }


  /**
   * Trigger a full consolidation cycle.
   * Runs radiance, co-activation drift, nucleus detection, abstraction generation.
   */
  async triggerConsolidation(): Promise<void> {
    try {
      const result = await this.field.consolidate()
      this.stats.consolidations++
      this.logger.info('Meditation consolidation complete', {
        potentiationUpdates: result.potentiationUpdates,
        nuclei: result.nucleiDetected,
        abstractions: result.abstractionsCreated,
      })
    } catch (err) {
      this.logger.warn('Meditation consolidation failed', { error: String(err) })
    }
  }
}
