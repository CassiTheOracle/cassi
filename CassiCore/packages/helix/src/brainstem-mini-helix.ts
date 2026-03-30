/**
 * Brainstem Mini-Helix — Sidecar observer for parent Helix sessions
 *
 * Constellation-managed lifecycle: the pipeline controls start/stop and
 * can reassign Brainstem mini-Helixes across branches. Default is 1:1
 * with a parent Helix, but the pipeline can override.
 *
 * The mini-Helix session observes the parent's work stream through
 * purpose-built tools (read_work_stream, read_annotations, etc.) and
 * publishes guidance + digest updates through the same tool interface.
 *
 * Unlike the legacy HelixBrainstem which uses raw LLM.complete() calls
 * in a tight loop, this runs a proper tool-calling agent that can make
 * structured decisions about what to observe and how to respond.
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type { WorkUnit } from '../dyad/types.js'
import type {
  BrainstemAnnotation,
  BrainstemConfig,
  BrainstemDeps,
  BrainstemState,
  BrainstemResult,
  GuidanceUrgency,
  SharedTreeReader,
} from './brainstem-types.js'
import {
  DEFAULT_BRAINSTEM_CONFIG,
  createInitialBrainstemState,
} from './brainstem-types.js'
import type { BranchApproach, CorpusDirective } from '../constellation/corpus-types.js'
import type {
  MiniHelixSession,
  MiniHelixDeps,
  MiniHelixConfig,
} from '../mini-helix/mini-helix-types.js'
import { createMiniHelixSession } from '../mini-helix/mini-helix-runner.js'
import {
  createBrainstemTools,
  buildBrainstemSystemPrompt,
} from './brainstem-tools.js'
import type { BrainstemToolContext } from './brainstem-tools.js'


// ═══════════════════════════════════════════════════════════════════
// Configuration
// ═══════════════════════════════════════════════════════════════════

/**
 * Configuration specific to the Brainstem mini-Helix mode.
 */
export interface BrainstemMiniHelixConfig {
  /** Model tier for the Brainstem mini-Helix. Default: 'fast' */
  modelTier?: string
  /** Model name override (e.g., 'gpt-5-mini'). Optional. */
  modelName?: string
  /** Max tool-call iterations per monitoring cycle. Default: 30 */
  maxIterationsPerCycle?: number
  /** Timeout per cycle in ms. Default: 60_000 */
  cycleTimeoutMs?: number
  /** Delay between monitoring cycles in ms. Default: 5_000 */
  cyclePollMs?: number
}


// ═══════════════════════════════════════════════════════════════════
// Brainstem Mini-Helix
// ═══════════════════════════════════════════════════════════════════

export class BrainstemMiniHelix {
  private session: MiniHelixSession | null = null
  private config: BrainstemMiniHelixConfig
  private state: BrainstemState
  private logger: ILogger

  // Parent observation
  private helixId: string
  private goal: string
  private constellationGoal: string
  private constellationId: string

  // Work unit tracking
  private workUnits: WorkUnit[] = []
  private annotations: BrainstemAnnotation[] = []
  private qualityTrajectory: number[] = []

  // Guidance count tracking
  private guidanceCount = 0
  private onInjectGuidance?: (content: string, urgency: GuidanceUrgency) => void

  // Shared tree (optional, constellation mode)
  private sharedTree?: SharedTreeReader
  private escalateToCorpus?: (reason: string, context: Record<string, unknown>) => void

  // Self-org state
  private currentApproach: BranchApproach = 'exploration'
  private recentFilesActive: Set<string> = new Set()

  // Lifecycle
  private running = false
  private shutdownRequested = false
  private cycleTimer: ReturnType<typeof setTimeout> | null = null

  // Dependencies for mini-Helix creation
  private miniHelixDeps: MiniHelixDeps

  constructor(opts: {
    helixId: string
    goal: string
    constellationGoal: string
    constellationId: string
    logger: ILogger
    miniHelixDeps: MiniHelixDeps
    sharedTree?: SharedTreeReader
    escalateToCorpus?: (reason: string, context: Record<string, unknown>) => void
    onInjectGuidance?: (content: string, urgency: GuidanceUrgency) => void
    config?: BrainstemMiniHelixConfig
  }) {
    this.helixId = opts.helixId
    this.goal = opts.goal
    this.constellationGoal = opts.constellationGoal
    this.constellationId = opts.constellationId
    this.logger = opts.logger.child(`brainstem-mini-helix:${opts.helixId}`)
    this.miniHelixDeps = opts.miniHelixDeps
    this.sharedTree = opts.sharedTree
    this.escalateToCorpus = opts.escalateToCorpus
    this.onInjectGuidance = opts.onInjectGuidance
    this.config = opts.config ?? {}
    this.state = createInitialBrainstemState()
  }


  // ─── Public API (Constellation pipeline manages these) ─────────

  /** Start the sidecar monitoring loop */
  async start(): Promise<void> {
    if (this.running) return
    this.running = true
    this.shutdownRequested = false

    this.logger.info('Brainstem mini-Helix starting', { helixId: this.helixId })

    // Build tool context
    const toolCtx = this.buildToolContext()

    // Create tools
    const tools = createBrainstemTools(toolCtx)

    // Create session
    const config: MiniHelixConfig = {
      consumer: 'brainstem',
      systemPrompt: buildBrainstemSystemPrompt(
        this.helixId,
        this.goal,
        this.constellationGoal,
      ),
      sessionId: `brainstem-${this.helixId}`,
      constellationId: this.constellationId,
      maxIterationsPerCycle: this.config.maxIterationsPerCycle ?? 30,
      maxTokens: 1024,
      cycleTimeoutMs: this.config.cycleTimeoutMs ?? 60_000,
      modelTier: this.config.modelTier ?? 'fast',
      modelName: this.config.modelName,
    }

    this.session = createMiniHelixSession(tools, config, this.miniHelixDeps)

    // Start monitoring loop
    await this.runMonitoringLoop()
  }

  /** Stop the sidecar */
  async stop(): Promise<void> {
    this.shutdownRequested = true
    this.running = false

    if (this.cycleTimer) {
      clearTimeout(this.cycleTimer)
      this.cycleTimer = null
    }

    if (this.session) {
      this.session.cancel()
      await this.session.shutdown()
      this.session = null
    }

    this.logger.info('Brainstem mini-Helix stopped', {
      helixId: this.helixId,
      totalAnnotations: this.annotations.length,
    })
  }

  /** Pause externally (constellation can pause brainstems) */
  pause(): void {
    if (this.session) {
      this.session.pause()
      if (this.cycleTimer) {
        clearTimeout(this.cycleTimer)
        this.cycleTimer = null
      }
      this.logger.info('Brainstem mini-Helix paused', { helixId: this.helixId })
    }
  }

  /** Resume externally */
  resume(): void {
    if (this.session) {
      this.session.resume()
      this.runMonitoringLoop().catch((err) => {
        this.logger.error('Resume cycle failed', { error: String(err) })
      })
      this.logger.info('Brainstem mini-Helix resumed', { helixId: this.helixId })
    }
  }

  /** Feed a work unit from the parent's work stream */
  pushWorkUnit(workUnit: WorkUnit): void {
    this.workUnits.push(workUnit)
    // Extract file paths for topic detection
    for (const f of workUnit.filesModified ?? []) {
      this.recentFilesActive.add(typeof f === 'string' ? f : f.path)
    }
  }

  /** Feed a Corpus directive */
  onCorpusDirective(directive: CorpusDirective): void {
    // Inject directive as guidance to the parent
    if (this.onInjectGuidance) {
      this.onInjectGuidance(
        `[Strategic directive: ${directive.type}] ${directive.text} (reason: ${directive.reason})`,
        directive.urgency,
      )
    }
  }

  /** Get progress */
  getProgress() {
    return this.session?.getProgress() ?? null
  }

  /** Get result summary */
  getResult(): BrainstemResult {
    return {
      annotations: [...this.annotations],
      qualityTrajectory: [...this.qualityTrajectory],
      patternDetections: 0,
      guidanceInjections: this.guidanceCount,
      averageScore: this.qualityTrajectory.length > 0
        ? this.qualityTrajectory.reduce((a, b) => a + b, 0) / this.qualityTrajectory.length
        : 0,
      axonSteps: this.annotations.length,
      durationMs: 0,
    }
  }


  // ─── Internal ──────────────────────────────────────────────────

  private async runMonitoringLoop(): Promise<void> {
    if (!this.session || this.shutdownRequested) return

    try {
      const result = await this.session.run()

      this.logger.debug('Brainstem cycle completed', {
        helixId: this.helixId,
        status: result.status,
        toolCalls: result.toolCalls,
      })

      // Schedule next cycle if still running
      if (this.running && !this.shutdownRequested) {
        const delay = this.config.cyclePollMs ?? 5_000
        this.cycleTimer = setTimeout(() => {
          this.runMonitoringLoop().catch((err) => {
            this.logger.error('Monitoring cycle failed', { error: String(err) })
          })
        }, delay)
      }
    } catch (err) {
      this.logger.error('Brainstem cycle error', {
        helixId: this.helixId,
        error: String(err),
      })
    }
  }

  private buildToolContext(): BrainstemToolContext {
    return {
      helixId: this.helixId,
      goal: this.goal,
      logger: this.logger,

      getRecentWorkUnits: () => this.workUnits.slice(-10),
      getAllWorkUnits: () => this.workUnits,
      getAnnotations: () => this.annotations,
      getQualityTrajectory: () => this.qualityTrajectory,

      injectGuidance: (content: string, urgency: GuidanceUrgency) => {
        if (this.onInjectGuidance) {
          this.onInjectGuidance(content, urgency)
        }
        this.guidanceCount++
      },

      sharedTree: this.sharedTree,
      escalateToCorpus: this.escalateToCorpus,

      currentApproach: this.currentApproach,
      recentFilesActive: this.recentFilesActive,
    }
  }
}
