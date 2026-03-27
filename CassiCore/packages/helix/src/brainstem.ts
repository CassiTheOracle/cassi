/**
 * HelixBrainstem — Cognitive Organizer for Helix Sessions
 *
 * The Brainstem replaces the Mentor. It runs its own async LLM loop
 * (balanced tier) to:
 *   1. Automatically maintain Unity's axon tree from work units
 *   2. Score and annotate every work unit
 *   3. Detect pathological patterns (paralysis, drift, stalling)
 *   4. Synthesize reviewer dialectic into actionable guidance
 *   5. Produce training data (scored annotations)
 *
 * Topology:
 *   Unity (top) → work units → Brainstem (middle) → reviewers (bottom)
 *   Brainstem → guidance injection → Unity
 *   Reviewers → dialectic → Brainstem → synthesis → Unity
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type { WorkUnit } from '../dyad/types.js'
import type { CorpusDirective } from '../constellation/corpus-types.js'
import type {
  BrainstemConfig,
  BrainstemDeps,
  BrainstemState,
  BrainstemResult,
  BrainstemAnnotation,
  BrainstemBlackboard,
  BrainstemLLM,
  PendingGuidance,
  WorkUnitAnnotation,
  DetectedPattern,
  GuidanceUrgency,
} from './brainstem-types.js'
import {
  DEFAULT_BRAINSTEM_CONFIG,
  createInitialBrainstemState,
} from './brainstem-types.js'

/**
 * Queue item for work units waiting to be processed
 */
interface WorkUnitQueueItem {
  workUnit: WorkUnit
  unityIteration: number
}

/**
 * HelixBrainstem — Cognitive organizer that scores work units,
 * detects patterns, and produces guidance for Unity.
 */
export class HelixBrainstem {
  private deps: BrainstemDeps
  private config: BrainstemConfig
  private state: BrainstemState
  private logger: ILogger

  // Async loop control
  private running = false
  private shutdownRequested = false
  private loopPromise: Promise<void> | null = null

  // Queues
  private workUnitQueue: WorkUnitQueueItem[] = []
  private dialecticQueue: string[] = []
  private guidanceQueue: PendingGuidance[] = []

  // Dialectic accumulation
  private recentDialectic: string[] = []
  private readonly maxDialecticHistory = 10

  // Timing
  private startTime = 0

  constructor(deps: BrainstemDeps, config?: Partial<BrainstemConfig>) {
    this.deps = deps
    this.config = { ...DEFAULT_BRAINSTEM_CONFIG, ...config }
    this.state = createInitialBrainstemState()
    this.logger = deps.logger.child('HelixBrainstem')

    this.logger.info('Brainstem initialized', {
      sessionId: deps.sessionId,
      enabled: this.config.enabled,
    })
  }

  /**
   * Start the async Brainstem loop
   */
  async start(): Promise<void> {
    if (!this.config.enabled) {
      this.logger.info('Brainstem is disabled, skipping start')
      return
    }

    if (this.running) {
      this.logger.warn('Brainstem already running')
      return
    }

    this.running = true
    this.shutdownRequested = false
    this.startTime = Date.now()

    this.logger.info('Brainstem loop starting')

    this.loopPromise = this.runLoop()
  }

  /**
   * Stop the Brainstem loop gracefully
   */
  async stop(): Promise<void> {
    if (!this.running) {
      return
    }

    this.logger.info('Brainstem shutdown requested')
    this.shutdownRequested = true

    if (this.loopPromise) {
      await this.loopPromise
      this.loopPromise = null
    }

    this.running = false
    this.logger.info('Brainstem stopped', {
      durationMs: Date.now() - this.startTime,
      annotations: this.state.annotations.length,
    })
  }

  /**
   * Queue a work unit for processing
   */
  onWorkUnit(workUnit: WorkUnit, unityIteration: number): void {
    if (!this.config.enabled) {
      return
    }

    this.workUnitQueue.push({ workUnit, unityIteration })
    this.logger.debug('Work unit queued', {
      workUnitId: workUnit.id,
      iteration: unityIteration,
      queueLength: this.workUnitQueue.length,
    })
  }

  /**
   * Queue dialectic messages for synthesis
   */
  onDialecticUpdate(messages: string[]): void {
    if (!this.config.enabled || messages.length === 0) {
      return
    }

    this.dialecticQueue.push(...messages)
    this.logger.debug('Dialectic messages queued', {
      count: messages.length,
      queueLength: this.dialecticQueue.length,
    })
  }

  /**
   * Consume the latest guidance (one-shot)
   */
  getLatestGuidance(): PendingGuidance | null {
    return this.guidanceQueue.shift() ?? null
  }

  /**
   * Get current Brainstem state
   */
  getState(): BrainstemState {
    return { ...this.state }
  }

  /**
   * Get Brainstem result for final HelixResult
   */
  getResult(): BrainstemResult {
    const annotations = this.state.annotations
    const scores = this.state.qualityTrajectory
    const averageScore = scores.length > 0
      ? scores.reduce((a, b) => a + b, 0) / scores.length
      : 0

    return {
      annotations: [...annotations],
      qualityTrajectory: [...scores],
      patternDetections: this.state.totalPatternDetections,
      guidanceInjections: this.state.totalGuidanceCount,
      averageScore,
      axonSteps: this.state.currentAxonStep,
      durationMs: this.startTime > 0 ? Date.now() - this.startTime : 0,
    }
  }

  /**
   * Main async loop
   */
  private async runLoop(): Promise<void> {
    while (!this.shutdownRequested) {
      try {
        // Wait for work or idle poll
        const hasWork = await this.waitForWorkOrTimeout()

        if (this.shutdownRequested && !hasWork) {
          break
        }

        if (hasWork) {
          // Process all queued work units
          await this.processWorkUnitBatch()
        } else {
          // Idle poll - can perform maintenance
          this.logger.debug('Brainstem idle poll')
        }
      } catch (error) {
        this.logger.error('Error in Brainstem loop', {
          error: error instanceof Error ? error.message : String(error),
        })
        // Continue loop despite errors
      }
    }
  }

  /**
   * Wait for work to arrive or timeout
   */
  private async waitForWorkOrTimeout(): Promise<boolean> {
    const checkInterval = 100 // Check every 100ms
    const maxChecks = Math.ceil(this.config.idlePollMs / checkInterval)

    for (let i = 0; i < maxChecks; i++) {
      if (this.shutdownRequested) {
        return false
      }

      if (this.workUnitQueue.length > 0) {
        return true
      }

      await this.sleep(checkInterval)
    }

    return false
  }

  /**
   * Process a batch of queued work units
   */
  private async processWorkUnitBatch(): Promise<void> {
    // Collect work units to process
    const batch: WorkUnitQueueItem[] = []
    while (this.workUnitQueue.length > 0 && batch.length < 5) {
      const item = this.workUnitQueue.shift()
      if (item) {
        batch.push(item)
      }
    }

    if (batch.length === 0) {
      return
    }

    // Collect dialectic messages
    const dialecticBatch: string[] = []
    while (this.dialecticQueue.length > 0) {
      const msg = this.dialecticQueue.shift()
      if (msg) {
        dialecticBatch.push(msg)
      }
    }

    // Update recent dialectic history
    if (dialecticBatch.length > 0) {
      this.recentDialectic.push(...dialecticBatch)
      if (this.recentDialectic.length > this.maxDialecticHistory) {
        this.recentDialectic = this.recentDialectic.slice(-this.maxDialecticHistory)
      }
    }

    // Process each work unit
    for (const item of batch) {
      await this.processSingleWorkUnit(item, dialecticBatch)
    }
  }

  /**
   * Process a single work unit
   */
  private async processSingleWorkUnit(
    item: WorkUnitQueueItem,
    dialecticBatch: string[]
  ): Promise<void> {
    const { workUnit, unityIteration } = item

    this.state.workUnitsProcessed++
    this.state.currentAxonStep++

    try {
      // Build prompt
      const prompt = this.buildPrompt(workUnit, unityIteration, dialecticBatch)

      // Call LLM
      const response = await this.deps.llm.complete({
        prompt,
        modelTier: this.config.modelTier,
        maxTokens: this.config.maxTokens,
        timeoutMs: this.config.timeoutMs,
      })

      // Parse annotation
      const annotation = this.parseAnnotation(response.content, workUnit.id)

      // Update state
      this.updateState(annotation)

      // Handle pattern detection and guidance
      this.detectPatternsAndProduceGuidance(annotation)

      // Emit events for observability (cognitive feed, TUI, admin API)
      this.emitAnnotationEvent(annotation)

      // Push annotation to Corpus tree (Constellation mode only)
      this.pushToCorpusTree(annotation)

      // Post to blackboard if configured
      if (this.config.postToBlackboard) {
        this.postAnnotationToBlackboard(annotation)
      }

      this.logger.debug('Work unit processed', {
        workUnitId: workUnit.id,
        score: annotation.score,
        annotation: annotation.annotation,
        pattern: annotation.pattern,
      })
    } catch (error) {
      this.logger.error('Failed to process work unit', {
        workUnitId: workUnit.id,
        error: error instanceof Error ? error.message : String(error),
      })

      // Create fallback annotation on error
      const fallbackAnnotation: BrainstemAnnotation = {
        workUnitId: workUnit.id,
        score: 0.5,
        annotation: 'exploration',
        synthesis: '',
        pattern: 'none',
        guidance: null,
        guidanceUrgency: 'low',
        trainingNote: `Error processing work unit: ${error instanceof Error ? error.message : String(error)}`,
        axonStep: this.state.currentAxonStep,
        timestamp: Date.now(),
      }

      this.updateState(fallbackAnnotation)
    }
  }

  /**
   * Build LLM prompt for work unit analysis
   */
  private buildPrompt(
    workUnit: WorkUnit,
    unityIteration: number,
    dialecticBatch: string[]
  ): string {
    const toolCalls = workUnit.toolCalls.map(tc =>
      `- ${tc.name}: ${JSON.stringify(tc.input).slice(0, 200)}`
    ).join('\n')

    const toolResults = workUnit.toolResults.map(tr =>
      `- ${tr.isError ? '[ERROR]' : '[OK]'}: ${tr.content.slice(0, 200)}`
    ).join('\n')

    const filesChanged = workUnit.filesModified.map(fm =>
      `- ${fm.action}: ${fm.path}`
    ).join('\n')

    const dialecticSection = dialecticBatch.length > 0
      ? `\n## Recent Dialectic Messages\n${dialecticBatch.map(m => `- ${m.slice(0, 300)}`).join('\n')}`
      : ''

    const recentDialecticSection = this.recentDialectic.length > 0
      ? `\n## Dialectic Context (last ${this.recentDialectic.length})\n${this.recentDialectic.map(m => `- ${m.slice(0, 200)}`).join('\n')}`
      : ''

    return `I am the Brainstem — the cognitive organizer of this Helix session. I observe Unity's work, the reviewer dialectic, and the evolving thought chain. My job is to score, annotate, detect patterns, and guide.

## Session Goal
${this.deps.goal}

## Current Axon Step
${this.state.currentAxonStep}

## Work Unit to Analyze
- ID: ${workUnit.id}
- Unity Iteration: ${unityIteration}
- Timestamp: ${new Date(workUnit.timestamp).toISOString()}

## Unity's Reasoning
${workUnit.reasoning.slice(0, 1000)}

## Tool Calls
${toolCalls || '(none)'}

## Tool Results
${toolResults || '(none)'}

## Files Changed
${filesChanged || '(none)'}${dialecticSection}${recentDialecticSection}

## Quality Trajectory
Recent scores: ${this.state.qualityTrajectory.slice(-5).join(', ') || 'N/A'}
Consecutive explorations: ${this.state.consecutiveExplorations}
Consecutive drifts: ${this.state.consecutiveDrifts}

## Your Task
Analyze this work unit and provide:

SCORE: <number between 0 and 1>
ANNOTATION: <exploration|implementation|testing|revision|drift>
SYNTHESIS: <brief synthesis of reviewer dialectic, or NONE>
PATTERN: <none|paralysis|drift|convergence|stalling>
GUIDANCE: <specific guidance for Unity, or NONE>
TRAINING_NOTE: <human-readable note explaining your scoring>

Guidelines:
- Score based on progress toward goal, code quality, and appropriate tool use
- annotation: exploration=reading/searching, implementation=writing code, testing=verification, revision=fixing, drift=off-goal
- pattern: paralysis=reading without writing, drift=diverging from goal, stalling=repeating without progress, convergence=reviewers agree
- Provide guidance only if Unity needs correction or encouragement
- Be concise — this runs in a tight loop`;
  }

  /**
   * Parse LLM response into annotation fields
   */
  private parseAnnotation(response: string, workUnitId: string): BrainstemAnnotation {
    const scoreMatch = response.match(/SCORE:\s*([\d.]+)/i)
    const annotationMatch = response.match(/ANNOTATION:\s*(\w+)/i)
    const synthesisMatch = response.match(/SYNTHESIS:\s*([^\n]+)/i)
    const patternMatch = response.match(/PATTERN:\s*(\w+)/i)
    const guidanceMatch = response.match(/GUIDANCE:\s*([^\n]+)/i)
    const trainingNoteMatch = response.match(/TRAINING_NOTE:\s*([^\n]+)/i)

    // Parse score with bounds checking
    let score = 0.5
    if (scoreMatch) {
      const parsed = parseFloat(scoreMatch[1])
      if (!isNaN(parsed)) {
        score = Math.max(0, Math.min(1, parsed))
      }
    }

    // Parse annotation type
    const annotationType = annotationMatch?.[1]?.toLowerCase() as WorkUnitAnnotation
    const validAnnotations: WorkUnitAnnotation[] = ['exploration', 'implementation', 'testing', 'revision', 'drift']
    const annotation: WorkUnitAnnotation = validAnnotations.includes(annotationType)
      ? annotationType
      : 'exploration'

    // Parse pattern type
    const patternType = patternMatch?.[1]?.toLowerCase() as DetectedPattern
    const validPatterns: DetectedPattern[] = ['none', 'paralysis', 'drift', 'convergence', 'stalling']
    const pattern: DetectedPattern = validPatterns.includes(patternType)
      ? patternType
      : 'none'

    // Parse synthesis
    const synthesis = synthesisMatch?.[1]?.trim() ?? ''
    const normalizedSynthesis = synthesis.toUpperCase() === 'NONE' ? '' : synthesis

    // Parse guidance
    const guidanceText = guidanceMatch?.[1]?.trim() ?? null
    const guidance: string | null = guidanceText && guidanceText.toUpperCase() !== 'NONE'
      ? guidanceText
      : null

    // Determine urgency based on pattern and score
    let urgency: GuidanceUrgency = 'low'
    if (pattern === 'paralysis' || score < 0.3) {
      urgency = 'critical'
    } else if (pattern === 'drift' || score < 0.5) {
      urgency = 'high'
    } else if (pattern === 'stalling') {
      urgency = 'medium'
    }

    // Parse training note
    const trainingNote = trainingNoteMatch?.[1]?.trim() ?? 'No training note provided'

    return {
      workUnitId,
      score,
      annotation,
      synthesis: normalizedSynthesis,
      pattern,
      guidance,
      guidanceUrgency: urgency,
      trainingNote,
      axonStep: this.state.currentAxonStep,
      timestamp: Date.now(),
    }
  }

  /**
   * Update Brainstem state with new annotation
   */
  private updateState(annotation: BrainstemAnnotation): void {
    this.state.annotations.push(annotation)
    this.state.qualityTrajectory.push(annotation.score)

    // Update consecutive counters
    if (annotation.annotation === 'exploration') {
      this.state.consecutiveExplorations++
    } else {
      this.state.consecutiveExplorations = 0
    }

    if (annotation.annotation === 'drift') {
      this.state.consecutiveDrifts++
    } else {
      this.state.consecutiveDrifts = 0
    }

    // Update pattern detections
    if (annotation.pattern !== 'none') {
      this.state.totalPatternDetections++
    }
  }

  /**
   * Detect patterns and produce guidance if needed
   */
  private detectPatternsAndProduceGuidance(annotation: BrainstemAnnotation): void {
    // Check for paralysis pattern
    if (this.state.consecutiveExplorations >= this.config.paralysisThreshold) {
      this.state.totalPatternDetections++
      const guidance: PendingGuidance = {
        text: 'Stop reading and start implementing.',
        urgency: 'critical',
        fromStep: this.state.currentAxonStep,
        triggeredBy: 'paralysis',
        timestamp: Date.now(),
      }
      this.queueGuidance(guidance)
      this.state.consecutiveExplorations = 0 // Reset after producing guidance
      return
    }

    // Check for drift pattern
    if (this.state.consecutiveDrifts >= this.config.driftThreshold) {
      this.state.totalPatternDetections++
      const guidance: PendingGuidance = {
        text: `Refocus on the goal: ${this.deps.goal}. Current work appears to be diverging.`,
        urgency: 'high',
        fromStep: this.state.currentAxonStep,
        triggeredBy: 'drift',
        timestamp: Date.now(),
      }
      this.queueGuidance(guidance)
      this.state.consecutiveDrifts = 0 // Reset after producing guidance
      return
    }

    // Queue guidance from annotation if present
    if (annotation.guidance) {
      const guidance: PendingGuidance = {
        text: annotation.guidance,
        urgency: annotation.guidanceUrgency,
        fromStep: this.state.currentAxonStep,
        triggeredBy: annotation.pattern,
        timestamp: Date.now(),
      }
      this.queueGuidance(guidance)
    }
  }

  /**
   * Queue guidance with cooldown check
   */
  private queueGuidance(guidance: PendingGuidance): void {
    // Check cooldown
    const iterationsSinceLastGuidance = this.state.currentAxonStep - this.state.lastGuidanceStep
    if (iterationsSinceLastGuidance < this.config.guidanceCooldownIterations) {
      this.logger.debug('Guidance cooldown active, skipping', {
        urgency: guidance.urgency,
        cooldownRemaining: this.config.guidanceCooldownIterations - iterationsSinceLastGuidance,
      })
      return
    }

    this.guidanceQueue.push(guidance)
    this.state.lastGuidanceStep = this.state.currentAxonStep
    this.state.totalGuidanceCount++

    this.logger.info('Guidance produced', {
      urgency: guidance.urgency,
      triggeredBy: guidance.triggeredBy,
      text: guidance.text.slice(0, 100),
    })

    // Emit guidance event
    this.emitEvent('brainstem:guidance', {
      urgency: guidance.urgency,
      triggeredBy: guidance.triggeredBy,
      text: guidance.text,
      axonStep: guidance.fromStep,
      timestamp: new Date(),
    })
  }

  // ── Event Emission ──────────────────────────────────────────────────

  /**
   * Emit brainstem:annotation event (and brainstem:pattern if non-none).
   */
  private emitAnnotationEvent(annotation: BrainstemAnnotation): void {
    this.emitEvent('brainstem:annotation', {
      workUnitId: annotation.workUnitId,
      score: annotation.score,
      annotation: annotation.annotation,
      pattern: annotation.pattern,
      guidance: annotation.guidance ?? undefined,
      axonStep: annotation.axonStep,
      timestamp: new Date(annotation.timestamp),
    })

    if (annotation.pattern !== 'none') {
      const severity = annotation.pattern === 'paralysis' || annotation.pattern === 'stalling'
        ? 'high'
        : annotation.pattern === 'drift'
          ? 'medium'
          : 'low'
      this.emitEvent('brainstem:pattern', {
        pattern: annotation.pattern,
        severity,
        axonStep: annotation.axonStep,
        timestamp: new Date(annotation.timestamp),
      })
    }
  }

  /**
   * Emit an event on the event bus if available.
   */
  private emitEvent(type: string, data: Record<string, unknown>): void {
    if (!this.deps.eventBus) return
    try {
      void this.deps.eventBus.emit({
        type,
        sessionId: this.deps.sessionId,
        ...data,
      } as any)
    } catch {
      // Ignore emit errors — observability must not crash the loop
    }
  }

  // ── Corpus Tree Integration ──────────────────────────────────────────

  /**
   * Push annotation to the Corpus tree (Constellation mode only).
   * Each Brainstem builds its branch of the Corpus's reasoning tree.
   */
  private pushToCorpusTree(annotation: BrainstemAnnotation): void {
    if (!this.deps.corpusTree || !this.deps.helixId) return
    try {
      this.deps.corpusTree.pushAnnotation(this.deps.helixId, annotation)
    } catch (err) {
      this.logger.warn('Failed to push annotation to Corpus tree', {
        error: String(err),
        helixId: this.deps.helixId,
      })
    }
  }

  /**
   * Receive a directive from the Corpus (Constellation-level organizer).
   * Converts it to a PendingGuidance and queues it for Unity delivery
   * through the normal escalation model.
   */
  onCorpusDirective(directive: CorpusDirective): void {
    this.logger.info('Corpus directive received', {
      type: directive.type,
      urgency: directive.urgency,
      reason: directive.reason,
    })

    this.queueGuidance({
      urgency: directive.urgency,
      triggeredBy: `corpus:${directive.type}` as any,
      text: `[Corpus] ${directive.text}`,
      fromStep: this.state.currentAxonStep,
      timestamp: Date.now(),
    })
  }


  // ── Blackboard Posting ──────────────────────────────────────────────

  /**
   * Post annotation to blackboard for cross-posture visibility and training data.
   */
  private postAnnotationToBlackboard(annotation: BrainstemAnnotation): void {
    const bb = this.deps.blackboard
    if (!bb) {
      this.logger.debug('Annotation ready for blackboard (no blackboard wired)', {
        workUnitId: annotation.workUnitId,
        score: annotation.score,
      })
      return
    }

    try {
      // Patterns and low scores go to 'concerns', everything else to 'findings'
      const channel = annotation.pattern !== 'none' || annotation.score < 0.4
        ? 'concerns' as const
        : 'findings' as const

      const scoreEmoji = annotation.score >= 0.7 ? '🟢' : annotation.score >= 0.5 ? '🟡' : '🔴'

      bb.post(channel, {
        author: 'brainstem',
        content: `${scoreEmoji} **${annotation.annotation}** (${annotation.score.toFixed(2)}) — ${annotation.trainingNote}${annotation.synthesis ? `\n_Dialectic:_ ${annotation.synthesis}` : ''}${annotation.guidance ? `\n_Guidance:_ ${annotation.guidance}` : ''}`,
        structured: {
          workUnitId: annotation.workUnitId,
          score: annotation.score,
          annotation: annotation.annotation,
          pattern: annotation.pattern,
          axonStep: annotation.axonStep,
        },
        priority: annotation.pattern !== 'none' ? 2 : annotation.score < 0.5 ? 1 : 0,
        tags: [
          'brainstem',
          annotation.annotation,
          ...(annotation.pattern !== 'none' ? [annotation.pattern] : []),
        ],
      })
    } catch (err) {
      this.logger.warn('Failed to post annotation to blackboard', {
        error: String(err),
        workUnitId: annotation.workUnitId,
      })
    }
  }

  /**
   * Sleep helper
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

  /**
   * Force immediate processing of all queued work units (for testing and sync use).
   * Bypasses the async loop polling.
   */
  async processNow(): Promise<void> {
    if (!this.config.enabled) return
    await this.processWorkUnitBatch()
  }
}

/**
 * Factory function to create a HelixBrainstem instance
 */
export function createHelixBrainstem(
  deps: BrainstemDeps,
  config?: Partial<BrainstemConfig>
): HelixBrainstem {
  return new HelixBrainstem(deps, config)
}
