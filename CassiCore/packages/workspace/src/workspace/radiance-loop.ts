/**
 * RadianceLoop — Orchestrates the complete GWT feedback cycle.
 *
 * Coordinates the flow:
 *   1. Workspace broadcasts → modules respond with context
 *   2. Response Collector assembles the ResponsePattern
 *   3. Expectation Model scores surprise
 *   4. If surprised: LLM Observer produces metacognitive signals
 *   5. Observations enter workspace (CognitiveSignal) and Monitor (CorticalSignal)
 *   6. Loop restarts on next broadcast
 *
 * The RadianceLoop runs as part of the workspace tick cycle. It can also
 * be triggered manually for testing.
 *
 * Configuration: enabled via RadianceLoopConfig, defaults to off (opt-in).
 */

import type { ILogger, IEventBus } from '@cassicore/foundation'
import type { GlobalWorkspace } from './global-workspace.js'
import type { CorticalField } from '../vendor/core/intelligence/cortex/index.js'
import type { CognitiveSignal } from './cognitive-signal.js'
import type {
  ResponsePattern,
  SurpriseAssessment,
  ObservationSignal,
  RadianceLoopConfig,
} from './radiance-types.js'
import { DEFAULT_RADIANCE_LOOP_CONFIG } from './radiance-types.js'
import { ExpectationModel } from './expectation-model.js'
import { buildObserverPrompt, getObserverToolSchemas, buildObserverHandlers } from './workspace-observer.js'
import type { ToolCallResult } from '../vendor/core/intelligence/constellation/meditation/solo-runner.js'


/**
 * Result of a single radiance cycle.
 */
export interface RadianceCycleResult {
  /** The response pattern from this cycle */
  pattern: ResponsePattern
  /** Surprise assessment from the expectation model */
  surprise: SurpriseAssessment
  /** Whether the observer fired */
  observerFired: boolean
  /** Observations produced (empty if observer didn't fire) */
  observations: ObservationSignal[]
  /** Duration of the full cycle */
  durationMs: number
}


/**
 * Callback type for running the LLM observer.
 * Decoupled from SoloRunner to keep the RadianceLoop testable
 * without requiring a real LLM provider.
 */
export type ObserverRunner = (
  prompt: string,
  toolSchemas: Array<{ name: string; description: string; input_schema: Record<string, unknown> }>,
  handlers: Record<string, (input: Record<string, unknown>) => Promise<ToolCallResult>>,
  maxIterations: number,
) => Promise<void>


export class RadianceLoop {
  private config: RadianceLoopConfig
  private expectationModel: ExpectationModel
  private logger: ILogger
  private eventBus?: IEventBus
  private workspace: GlobalWorkspace
  private cortex?: CorticalField
  private observerRunner?: ObserverRunner

  private cycleCount = 0
  private lastCycleResult: RadianceCycleResult | null = null
  private totalObservations = 0

  constructor(
    workspace: GlobalWorkspace,
    logger: ILogger,
    config?: Partial<RadianceLoopConfig>,
  ) {
    this.workspace = workspace
    this.config = { ...DEFAULT_RADIANCE_LOOP_CONFIG, ...config }
    this.logger = logger.child ? logger.child('radiance') : logger
    this.expectationModel = new ExpectationModel(
      this.config.warmupCycles,
      this.config.learningRate,
    )
  }


  setCortex(cortex: CorticalField): void {
    this.cortex = cortex
  }

  setEventBus(bus: IEventBus): void {
    this.eventBus = bus
  }

  /**
   * Set the runner that invokes the LLM observer.
   * Decoupled from SoloRunner for testability — in production, this wraps
   * runSoloExplorer. In tests, it can be a mock or stub.
   */
  setObserverRunner(runner: ObserverRunner): void {
    this.observerRunner = runner
  }

  /**
   * Convenience: create an ObserverRunner from a handle factory.
   * Wraps SoloRunner to acquire a model handle, run the observer,
   * and release the handle when done.
   */
  setHandleFactory(
    factory: (config: { tier: string; purpose: string; sessionId: string }) => Promise<import('../vendor/core/intelligence/constellation/meditation/solo-runner.js').ModelHandle>,
    toolExecutor: import('../vendor/core/intelligence/constellation/meditation/solo-runner.js').ToolExecutor,
    toolRegistry: import('../vendor/core/intelligence/constellation/meditation/solo-runner.js').ToolRegistry,
    eventBus: IEventBus,
  ): void {
    this.observerRunner = async (prompt, toolSchemas, handlers, maxIterations) => {
      const { runSoloExplorer } = await import('../vendor/core/intelligence/constellation/meditation/solo-runner.js')

      const handle = await factory({
        tier: this.config.observerModelTier,
        purpose: 'radiance-observer',
        sessionId: `radiance-observer-${this.cycleCount}`,
      })

      await runSoloExplorer({
        sessionId: `radiance-observer-${this.cycleCount}`,
        name: 'radiance-observer',
        instruction: prompt,
        handle,
        toolExecutor,
        toolRegistry,
        maxIterations,
        logger: this.logger,
        eventBus,
        signal: new AbortController().signal,
        customHandlers: handlers,
        customToolSchemas: toolSchemas,
      })
    }
    this.logger.info('[Radiance] Observer handle factory configured')
  }


  /**
   * Run one full radiance cycle.
   *
   * Called after each workspace broadcast (typically once per turn).
   * Steps:
   *   1. Collect responses from all registered modules
   *   2. Score surprise against expectations
   *   3. Update the expectation model
   *   4. If surprise exceeds threshold: run the LLM observer
   *   5. Post observations to workspace and cortex
   */
  async cycle(): Promise<RadianceCycleResult> {
    const start = Date.now()
    this.cycleCount++

    const currentFoci = this.workspace.getCurrentFoci()
    if (currentFoci.length === 0) {
      const emptyResult: RadianceCycleResult = {
        pattern: {
          broadcastSignals: [],
          responses: [],
          unexpectedSilences: [],
          unexpectedResponses: [],
          convergentCount: 0, divergentCount: 0, lateralCount: 0, silentCount: 0,
          totalModules: 0,
          timestamp: Date.now(),
        },
        surprise: { composite: 0, perModule: [], shouldObserve: false, dominantSurprise: 'none' },
        observerFired: false,
        observations: [],
        durationMs: Date.now() - start,
      }
      this.lastCycleResult = emptyResult
      return emptyResult
    }

    // Step 1: Collect responses
    const pattern = await this.workspace.collectResponses(currentFoci)

    // Step 2: Score surprise
    const surprise = this.expectationModel.assess(pattern)

    // Step 3: Update expectations (always, even during warmup)
    this.expectationModel.update(pattern)

    // Step 4: Run observer if surprised
    let observations: ObservationSignal[] = []
    let observerFired = false

    if (surprise.shouldObserve && surprise.composite >= this.config.surpriseThreshold) {
      if (this.observerRunner) {
        observerFired = true
        observations = await this.runObserver(pattern, surprise)
      } else {
        this.logger.debug('[Radiance] Surprise detected but no observer runner configured', {
          surprise: surprise.composite.toFixed(2),
        })
      }
    }

    // Step 5: Post observations
    if (observations.length > 0) {
      this.postObservations(observations, pattern)
    }

    const result: RadianceCycleResult = {
      pattern,
      surprise,
      observerFired,
      observations,
      durationMs: Date.now() - start,
    }

    this.lastCycleResult = result

    if (observerFired) {
      this.logger.info('[Radiance] Cycle complete — observer fired', {
        cycle: this.cycleCount,
        surprise: surprise.composite.toFixed(2),
        dominant: surprise.dominantSurprise,
        observations: observations.length,
        durationMs: result.durationMs,
      })
    } else {
      this.logger.debug('[Radiance] Cycle complete — equanimity', {
        cycle: this.cycleCount,
        surprise: surprise.composite.toFixed(2),
        warmedUp: this.expectationModel.isWarmedUp(),
      })
    }

    this.emitCycleEvent(result)

    return result
  }


  private async runObserver(
    pattern: ResponsePattern,
    surprise: SurpriseAssessment,
  ): Promise<ObservationSignal[]> {
    const prompt = buildObserverPrompt(pattern, surprise)
    const toolSchemas = getObserverToolSchemas()
    const { handlers, observations } = buildObserverHandlers(this.logger, surprise.composite)

    try {
      await this.observerRunner!(
        prompt,
        toolSchemas,
        handlers,
        this.config.maxObserverIterations,
      )
    } catch (err) {
      this.logger.warn('[Radiance] Observer runner failed', { error: String(err) })
    }

    return observations
  }


  /**
   * Post observations to workspace (as CognitiveSignals) and cortex (as CorticalSignals).
   */
  private postObservations(observations: ObservationSignal[], pattern: ResponsePattern): void {
    for (const obs of observations) {
      this.totalObservations++

      // Post to GlobalWorkspace as a CognitiveSignal
      if (this.config.submitToWorkspace) {
        const signal: CognitiveSignal = {
          signalId: `monitor-${this.cycleCount}-${this.totalObservations}`,
          source: 'monitor',
          sessionId: '*',
          type: obs.observationType === 'tension' ? 'tension'
            : obs.observationType === 'convergence' ? 'convergence'
            : obs.observationType === 'novelty' ? 'enrichment'
            : obs.observationType === 'absence' ? 'warning'
            : obs.observationType === 'self-reference' ? 'observation'
            : 'insight',
          content: obs.narrative,
          luminance: { novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0, cognitiveResonance: 0, strategicImportance: 0, composite: 0 },
          createdAt: Date.now(),
          metadata: {
            observationType: obs.observationType,
            surpriseScore: obs.surpriseScore,
            contributingSources: obs.contributingSources,
            isSelfReferential: obs.isSelfReferential,
          },
        }

        this.workspace.submit(signal)
      }

      // Post to Cortex Monitor region as a CorticalSignal
      if (this.config.postToMonitor && this.cortex) {
        try {
          this.cortex.signal('monitor', {
            type: obs.observationType === 'tension' ? 'anomaly'
              : obs.observationType === 'absence' ? 'concern'
              : 'insight',
            content: obs.narrative,
            author: 'radiance-observer',
            salience: obs.confidence,
            tags: ['radiance', obs.observationType, ...obs.contributingSources],
          })
        } catch (err) {
          this.logger.warn('[Radiance] Failed to post to cortex monitor', { error: String(err) })
        }
      }
    }
  }


  // Introspection

  getConfig(): RadianceLoopConfig {
    return { ...this.config }
  }

  getCycleCount(): number {
    return this.cycleCount
  }

  getLastCycleResult(): RadianceCycleResult | null {
    return this.lastCycleResult
  }

  getExpectationModel(): ExpectationModel {
    return this.expectationModel
  }

  isWarmedUp(): boolean {
    return this.expectationModel.isWarmedUp()
  }

  getStats(): {
    cycleCount: number
    totalObservations: number
    warmedUp: boolean
    expectations: number
    lastSurprise: number | null
    lastObserverFired: boolean
  } {
    return {
      cycleCount: this.cycleCount,
      totalObservations: this.totalObservations,
      warmedUp: this.isWarmedUp(),
      expectations: this.expectationModel.getAllExpectations().length,
      lastSurprise: this.lastCycleResult?.surprise.composite ?? null,
      lastObserverFired: this.lastCycleResult?.observerFired ?? false,
    }
  }

  reset(): void {
    this.expectationModel.reset()
    this.cycleCount = 0
    this.totalObservations = 0
    this.lastCycleResult = null
  }


  // Events

  private emitCycleEvent(result: RadianceCycleResult): void {
    if (!this.eventBus) return
    try {
      void (this.eventBus as any).emit({
        type: 'radiance:cycle',
        cycle: this.cycleCount,
        surprise: result.surprise.composite,
        dominantSurprise: result.surprise.dominantSurprise,
        observerFired: result.observerFired,
        observationCount: result.observations.length,
        responseCount: result.pattern.responses.length,
        convergent: result.pattern.convergentCount,
        divergent: result.pattern.divergentCount,
        lateral: result.pattern.lateralCount,
        silent: result.pattern.silentCount,
        durationMs: result.durationMs,
        timestamp: Date.now(),
      })
    } catch {
      // fire-and-forget
    }
  }
}
